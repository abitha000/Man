import asyncio
import contextlib
from io import BytesIO
import re
from tg_bot.modules.helper_funcs.chat_status import dev_plus, sudo_plus
from tg_bot.modules.helper_funcs.decorators import rate_limit, kigyo_handler
import time
import tg_bot.modules.sql.users_sql as sql
from tg_bot import DEV_USERS, log, OWNER_ID, redis_client
import tg_bot
from tg_bot.modules.helper_funcs.msg_types import Types
from telegram import TelegramError, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import BadRequest
from telegram.ext import ContextTypes, CommandHandler, filters, MessageHandler, ChatMemberHandler, CallbackQueryHandler

USERS_GROUP = 4
CHAT_GROUP = 5
DEV_AND_MORE = DEV_USERS.append(int(OWNER_ID))


def parse_markdown_buttons(text):
    buttons = []
    current_row = []
    pattern = r'\[([^\]]+)\]\(buttonurl:([^)]+?)(:same)?\)'
    for match in re.finditer(pattern, text):
        btn_text = match.group(1)
        url = match.group(2)
        same = match.group(3) is not None
        if same and current_row:
            current_row.append(InlineKeyboardButton(btn_text, url=url))
        else:
            if current_row:
                buttons.append(current_row)
                current_row = []
            current_row.append(InlineKeyboardButton(btn_text, url=url))
    if current_row:
        buttons.append(current_row)
    text = re.sub(pattern, '', text).strip()
    markup = InlineKeyboardMarkup(buttons) if buttons else None
    return text, markup


async def send_broadcast_messages(context, queue_key, msg_text, meta_key, lock_key, target_type):
    failed = 0
    text, markup = parse_markdown_buttons(msg_text)
    data_type = int((await redis_client.hget(meta_key, "data_type")))
    content = (await redis_client.hget(meta_key, "content")) or None
    while True:
        status = await redis_client.hget(meta_key, "status")
        if status and status != "running":
            break
        nxt = await redis_client.lpop(queue_key)
        if not nxt:
            break
        try:
            if data_type in (Types.BUTTON_TEXT, Types.TEXT):
                await context.bot.send_message(
                    int(nxt),
                    text,
                    parse_mode="MARKDOWN",
                    disable_web_page_preview=True,
                    reply_markup=markup,
                )
            elif data_type == Types.STICKER:
                await context.bot.send_sticker(
                    int(nxt),
                    content,
                    reply_markup=markup,
                )
            else:
                send_func_map = {
                    Types.DOCUMENT.value: context.bot.send_document,
                    Types.PHOTO.value: context.bot.send_photo,
                    Types.AUDIO.value: context.bot.send_audio,
                    Types.VOICE.value: context.bot.send_voice,
                    Types.VIDEO.value: context.bot.send_video,
                }
                func = send_func_map.get(data_type)
                if func:
                    await func(
                        int(nxt),
                        content,
                        caption=text,
                        parse_mode="MARKDOWN",
                        disable_web_page_preview=True,
                        reply_markup=markup,
                    )
            await redis_client.hincrby(meta_key, f"sent_{target_type}", 1)
        except BadRequest:
            try:
                if data_type in (Types.BUTTON_TEXT, Types.TEXT):
                    await context.bot.send_message(
                        int(nxt),
                        text,
                        disable_web_page_preview=True,
                        reply_markup=markup,
                    )
                elif data_type == Types.STICKER:
                    await context.bot.send_sticker(
                        int(nxt),
                        content,
                        reply_markup=markup,
                    )
                else:
                    func = send_func_map.get(data_type)
                    if func:
                        await func(
                            int(nxt),
                            content,
                            caption=text,
                            disable_web_page_preview=True,
                            reply_markup=markup,
                        )
                await redis_client.hincrby(meta_key, f"sent_{target_type}", 1)
            except TelegramError:
                failed += 1
                await redis_client.hincrby(meta_key, f"failed_{target_type}", 1)
        except TelegramError:
            failed += 1
            await redis_client.hincrby(meta_key, f"failed_{target_type}", 1)
        await redis_client.hset(meta_key, "updated_at", int(time.time()))
        await redis_client.expire(lock_key, 3600)
        await asyncio.sleep(0.1)
    return failed


async def perform_broadcast(context, meta_key, lock_key, gq_key, uq_key, msg_text, to_group, to_user):
    await redis_client.hset(meta_key, "status", "running")
    failed_g = 0
    failed_u = 0
    if to_group:
        failed_g = await send_broadcast_messages(context, gq_key, msg_text, meta_key, lock_key, "groups")
    if to_user:
        failed_u = await send_broadcast_messages(context, uq_key, msg_text, meta_key, lock_key, "users")
    status = await redis_client.hget(meta_key, "status")
    status = status if status else "completed"
    if status == "running":
        await redis_client.hset(meta_key, "status", "completed")
    await redis_client.delete(lock_key)
    return failed_g, failed_u, status


async def get_user_id(username):
    if len(username) <= 5:
        return None

    if username.startswith("@"):
        username = username[1:]

    users = sql.get_userid_by_name(username)

    if not users:
        return None

    elif len(users) == 1:
        return users[0]

    else:
        for user_obj in users:
            try:
                userdat = await tg_bot.application.bot.get_chat(user_obj)
                if userdat.username == username:
                    return userdat.id

            except BadRequest as excp:
                if excp.message != "Chat not found":
                    log.exception("Error extracting user ID")

    return None


@dev_plus
@rate_limit(40, 60)
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    to_send = update.effective_message.text.split(None, 1)

    if len(to_send) >= 2 or update.effective_message.reply_to_message:
        cmd = to_send[0]
        to_group = cmd == "/broadcastgroups" or cmd == "/broadcastall"
        to_user = cmd == "/broadcastusers" or cmd == "/broadcastall"
        if cmd not in ["/broadcastgroups", "/broadcastusers", "/broadcastall"]:
            to_group = to_user = True

        if update.effective_message.reply_to_message:
            replied = update.effective_message.reply_to_message
            if replied.sticker:
                data_type = Types.STICKER
                content = replied.sticker.file_id
                text = ""
            elif replied.document:
                data_type = Types.DOCUMENT
                content = replied.document.file_id
                text = replied.caption or ""
            elif replied.photo:
                data_type = Types.PHOTO
                content = replied.photo[-1].file_id
                text = replied.caption or ""
            elif replied.audio:
                data_type = Types.AUDIO
                content = replied.audio.file_id
                text = replied.caption or ""
            elif replied.voice:
                data_type = Types.VOICE
                content = replied.voice.file_id
                text = replied.caption or ""
            elif replied.video:
                data_type = Types.VIDEO
                content = replied.video.file_id
                text = replied.caption or ""
            else:
                msg_text = replied.text or replied.caption or ""
                text, markup = parse_markdown_buttons(msg_text)
                data_type = Types.BUTTON_TEXT if markup else Types.TEXT
                content = None
        else:
            msg_text = to_send[1]
            text, markup = parse_markdown_buttons(msg_text)
            data_type = Types.BUTTON_TEXT if markup else Types.TEXT
            content = None

        meta_key = "broadcast:meta"
        lock_key = "broadcast:lock"
        gq_key = "broadcast:groups"
        uq_key = "broadcast:users"
        existing = await redis_client.hgetall(meta_key)
        if existing and existing.get("status", "") in ["running", "paused", "pending_confirmation"]:
            await update.effective_message.reply_text("A broadcast is in progress. Use /broadcaststatus or /broadcastresume.")
            return
        if to_group:
            await redis_client.delete(gq_key)
            for c in sql.get_all_chats() or []:
                await redis_client.rpush(gq_key, int(c))
        if to_user:
            await redis_client.delete(uq_key)
            for u in sql.get_all_users() or []:
                await redis_client.rpush(uq_key, int(u))
        total_groups = await redis_client.llen(gq_key) if to_group else 0
        total_users = await redis_client.llen(uq_key) if to_user else 0
        if update.effective_message.reply_to_message:
            replied = update.effective_message.reply_to_message
            if replied.sticker or replied.document or replied.photo or replied.audio or replied.voice or replied.video:
                message_text = text
            else:
                message_text = msg_text
        else:
            message_text = msg_text
        await redis_client.hset(
            meta_key,
            mapping={
                "message": message_text,
                "to_group": int(to_group),
                "to_user": int(to_user),
                "total_groups": int(total_groups),
                "total_users": int(total_users),
                "sent_groups": 0,
                "sent_users": 0,
                "failed_groups": 0,
                "failed_users": 0,
                "status": "pending_confirmation",
                "admin_id": update.effective_user.id,
                "started_at": int(time.time()),
                "updated_at": int(time.time()),
                "data_type": int(data_type),
                "content": content or "",
            },
        )
        keyboard = [
            [InlineKeyboardButton("Confirm Broadcast", callback_data="broadcast_confirm")],
            [InlineKeyboardButton("Cancel", callback_data="broadcast_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        preview_text, _ = parse_markdown_buttons(text)
        preview_text = f"Broadcast Preview:\n\n{preview_text}\n\nTargets:\nGroups: {total_groups}\nUsers: {total_users}\n\nConfirm to start broadcasting?"
        await update.effective_message.reply_text(preview_text, reply_markup=reply_markup, parse_mode="MARKDOWN")
        return


@dev_plus
@rate_limit(20, 30)
async def broadcast_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    meta = await redis_client.hgetall("broadcast:meta")
    if not meta:
        await update.effective_message.reply_text("No broadcast state.")
        return
    m = meta
    tg = int(m.get("total_groups", 0) or 0)
    tu = int(m.get("total_users", 0) or 0)
    sg = int(m.get("sent_groups", 0) or 0)
    su = int(m.get("sent_users", 0) or 0)
    fg = int(m.get("failed_groups", 0) or 0)
    fu = int(m.get("failed_users", 0) or 0)
    rg = await redis_client.llen("broadcast:groups") if int(m.get("to_group", 0)) else 0
    ru = await redis_client.llen("broadcast:users") if int(m.get("to_user", 0)) else 0
    status = m.get("status", "unknown")
    await update.effective_message.reply_text(
        f"Status: {status}\nGroups: {sg}/{tg} (left {rg}), failed {fg}\nUsers: {su}/{tu} (left {ru}), failed {fu}"
    )


@dev_plus
@rate_limit(40, 60)
async def broadcast_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    meta_key = "broadcast:meta"
    lock_key = "broadcast:lock"
    gq_key = "broadcast:groups"
    uq_key = "broadcast:users"
    meta = await redis_client.hgetall(meta_key)
    if not meta:
        await update.effective_message.reply_text("No broadcast to resume.")
        return
    m = meta
    if m.get("status") == "completed" or (await redis_client.llen(gq_key) == 0 and await redis_client.llen(uq_key) == 0):
        await update.effective_message.reply_text("Broadcast already completed.")
        return
    if not await redis_client.set(lock_key, str(int(time.time())), nx=True, ex=3600):
        await update.effective_message.reply_text("Another broadcast is running. Try again later.")
        return
    await redis_client.hset(meta_key, "status", "running")
    msg_text = m.get("message", "")
    to_group = bool(int(m.get("to_group", 0)))
    to_user = bool(int(m.get("to_user", 0)))
    failed_g, failed_u, final_status = await perform_broadcast(context, meta_key, lock_key, gq_key, uq_key, msg_text, to_group, to_user)
    if final_status == "killed":
        await update.effective_message.reply_text(
            f"Broadcast was killed.\nGroups failed: {failed_g}.\nUsers failed: {failed_u}."
        )
    else:
        await update.effective_message.reply_text(
            f"Broadcast complete.\nGroups failed: {failed_g}.\nUsers failed: {failed_u}."
        )


@dev_plus
@rate_limit(40, 60)
async def broadcast_kill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    meta_key = "broadcast:meta"
    meta = await redis_client.hgetall(meta_key)
    if not meta:
        await update.effective_message.reply_text("No broadcast in progress.")
        return
    m = meta
    if m.get("status") != "running":
        await update.effective_message.reply_text("Broadcast is not currently running.")
        return
    await redis_client.hset(meta_key, "status", "killed")
    await update.effective_message.reply_text("Broadcast has been killed. It will stop shortly.")


@dev_plus
async def broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    data = query.data
    meta_key = "broadcast:meta"
    lock_key = "broadcast:lock"
    gq_key = "broadcast:groups"
    uq_key = "broadcast:users"
    meta = await redis_client.hgetall(meta_key)
    if not meta:
        await query.answer("No pending broadcast.")
        return
    m = meta
    if str(user.id) != m.get("admin_id"):
        await query.answer("You are not authorized to confirm this broadcast.")
        return
    if data == "broadcast_confirm":
        if m.get("status") != "pending_confirmation":
            await query.answer("Broadcast already processed.")
            return
        if not await redis_client.set(lock_key, str(int(time.time())), nx=True, ex=3600):
            await query.answer("Another broadcast is running.")
            return
        msg_text = m.get("message", "")
        to_group = bool(int(m.get("to_group", 0)))
        to_user = bool(int(m.get("to_user", 0)))
        failed_g, failed_u, final_status = await perform_broadcast(context, meta_key, lock_key, gq_key, uq_key, msg_text, to_group, to_user)
        if final_status == "killed":
            await query.edit_message_text(f"Broadcast was killed.\nGroups failed: {failed_g}.\nUsers failed: {failed_u}.")
        else:
            await query.edit_message_text(f"Broadcast complete.\nGroups failed: {failed_g}.\nUsers failed: {failed_u}.")
        await query.answer()
    elif data == "broadcast_cancel":
        await redis_client.delete(meta_key)
        await redis_client.delete(gq_key)
        await redis_client.delete(uq_key)
        await query.edit_message_text("Broadcast cancelled.")
        await query.answer()


async def welcomeFilter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ["group", "supergroup"]:
        return
    if nm := update.chat_member.new_chat_member:
        om = update.chat_member.old_chat_member
    if (nm.status, om.status) in [(nm.MEMBER, nm.KICKED), (nm.MEMBER, nm.LEFT), (nm.KICKED, nm.MEMBER),
                                  (nm.KICKED, nm.ADMINISTRATOR), (nm.KICKED, nm.CREATOR), (nm.LEFT, nm.MEMBER),
                                  (nm.LEFT, nm.ADMINISTRATOR), (nm.LEFT, nm.CREATOR)]:
        return await log_user(update, context)

@rate_limit(30, 60)
async def log_user(update: Update, _: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message

    if not msg and update.chat_member:
        sql.update_user(update.effective_user.id, update.effective_user.username, chat.id, chat.title)
        return

    sql.update_user(msg.from_user.id, msg.from_user.username, chat.id, chat.title)

    if rep := msg.reply_to_message:
        sql.update_user(
            rep.from_user.id,
            rep.from_user.username,
            chat.id,
            chat.title,
        )

        if rep.forward_from:
            sql.update_user(
                rep.forward_from.id,
                rep.forward_from.username,
            )

        if rep.entities:
            for entity in rep.entities:
                if entity.type in ["text_mention", "mention"]:
                    with contextlib.suppress(AttributeError):
                        sql.update_user(entity.user.id, entity.user.username)
        if rep.sender_chat and not rep.is_automatic_forward:
            sql.update_user(
                rep.sender_chat.id,
                rep.sender_chat.username,
                chat.id,
                chat.title,
            )

    if msg.forward_from:
        sql.update_user(msg.forward_from.id, msg.forward_from.username)

    if msg.entities:
        for entity in msg.entities:
            if entity.type in ["text_mention", "mention"]:
                with contextlib.suppress(AttributeError):
                    sql.update_user(entity.user.id, entity.user.username)
    if msg.sender_chat and not msg.is_automatic_forward:
        sql.update_user(msg.sender_chat.id, msg.sender_chat.username, chat.id, chat.title)

    if msg.new_chat_members:
        for user in msg.new_chat_members:
            if user.id == msg.from_user.id:
                continue
            sql.update_user(user.id, user.username, chat.id, chat.title)


@sudo_plus
@rate_limit(40, 60)
async def chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    all_chats = sql.get_all_chats() or []
    chatfile = "List of chats.\n0. Chat name | Chat ID | Members count\n"
    P = 1
    for chat in all_chats:
        try:
            curr_chat = await context.bot.get_chat(chat.chat_id)
            bot_member = await curr_chat.get_member(context.bot.id)
            chat_members = await curr_chat.get_member_count()
            chatfile += "{}. {} | {} | {}\n".format(
                P, chat.chat_name, chat.chat_id, chat_members
            )
            P += 1
        except Exception:
            pass

    with BytesIO(str.encode(chatfile)) as output:
        output.name = "glist.txt"
        await update.effective_message.reply_document(
            document=output,
            filename="glist.txt",
            caption="Here be the list of groups in my database.",
        )

@rate_limit(50, 60)
async def chat_checker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    if (await update.effective_message.chat.get_member(bot.id)).can_send_messages is False:
        await bot.leave_chat(update.effective_message.chat.id)


def __user_info__(user_id):
    if user_id in [777000, 1087968824]:
        return """Groups count: <code>N/A</code>"""
    num_chats = sql.get_user_num_chats(user_id)
    return f"""Groups count: <code>{num_chats}</code>"""


def __stats__():
    return f"• {sql.num_users()} users, across {sql.num_chats()} chats"


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


__help__ = ""

BROADCAST_HANDLER = CommandHandler(
    ["broadcastall", "broadcastusers", "broadcastgroups"], broadcast
)
BROADCST_STATUS_HANDLER = CommandHandler(
    ["broadcaststatus"], broadcast_status
)
BROADCST_RESUME_HANDLER = CommandHandler(
    ["broadcastresume"], broadcast_resume
)
BROADCAST_KILL_HANDLER = CommandHandler(
    ["broadcastkill"], broadcast_kill
)
BROADCAST_CALLBACK_HANDLER = CallbackQueryHandler(broadcast_callback, pattern=r"broadcast_(confirm|cancel)")
USER_HANDLER = MessageHandler(
    filters.ALL & filters.ChatType.GROUPS & ~filters.User(777000), log_user
)
CHAT_CHECKER_HANDLER = MessageHandler(
    filters.ALL & filters.ChatType.GROUPS & ~filters.User(777000), chat_checker
)

kigyo_handler._add_handler(
    ChatMemberHandler(
        welcomeFilter, ChatMemberHandler.CHAT_MEMBER
    ), group=110)

kigyo_handler._add_handler(USER_HANDLER, USERS_GROUP)
kigyo_handler._add_handler(BROADCAST_HANDLER)
kigyo_handler._add_handler(BROADCST_STATUS_HANDLER)
kigyo_handler._add_handler(BROADCST_RESUME_HANDLER)
kigyo_handler._add_handler(BROADCAST_KILL_HANDLER)
kigyo_handler._add_handler(BROADCAST_CALLBACK_HANDLER)
kigyo_handler._add_handler(CHAT_CHECKER_HANDLER, CHAT_GROUP)

__mod_name__ = "Users"
__handlers__ = [(USER_HANDLER, USERS_GROUP), BROADCAST_HANDLER, BROADCST_STATUS_HANDLER, BROADCST_RESUME_HANDLER, BROADCAST_KILL_HANDLER, BROADCAST_CALLBACK_HANDLER]
