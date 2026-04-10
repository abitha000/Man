import contextlib
from functools import wraps

from tg_bot import (
    DEL_CMDS,
    DEV_USERS,
    SUDO_USERS,
    SUPPORT_USERS,
    SARDEGNA_USERS,
    WHITELIST_USERS,
)
from telegram.constants import ChatMemberStatus
from cachetools import TTLCache
from telegram import Chat, ChatMember, Update, User
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from telegram.error import BadRequest, TelegramError

ADMIN_CACHE = TTLCache(maxsize=512, ttl=60 * 10)


async def is_anon(user: User, chat: Chat):
    return (await chat.get_member(user.id)).is_anonymous


def is_whitelist_plus(_: Chat, user_id: int) -> bool:
    return any(
        user_id in user
        for user in [
            WHITELIST_USERS,
            SARDEGNA_USERS,
            SUPPORT_USERS,
            SUDO_USERS,
            DEV_USERS,
        ]
    )


def is_support_plus(_: Chat, user_id: int) -> bool:
    return user_id in SUPPORT_USERS or user_id in SUDO_USERS or user_id in DEV_USERS


def is_sudo_plus(_: Chat, user_id: int) -> bool:
    return user_id in SUDO_USERS or user_id in DEV_USERS


def is_user_admin(update: Update, user_id: int, member: ChatMember = None) -> bool:
    chat = update.effective_chat
    msg = update.effective_message
    if (
            chat.type == "private"
            or user_id in SUDO_USERS
            or user_id in DEV_USERS
            or chat.all_members_are_administrators
            or (msg.reply_to_message and msg.reply_to_message.sender_chat is not None and
                msg.reply_to_message.sender_chat.type != "channel")
    ):
        return True

    if not member:
        try:
            return user_id in ADMIN_CACHE[chat.id]
        except KeyError:
            return False

    return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)


async def is_user_admin_async(update: Update, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    msg = update.effective_message
    if (
            chat.type == "private"
            or user_id in SUDO_USERS
            or user_id in DEV_USERS
            or chat.all_members_are_administrators
            or (msg.reply_to_message and msg.reply_to_message.sender_chat is not None and
                msg.reply_to_message.sender_chat.type != "channel")
    ):
        return True

    try:
        return user_id in ADMIN_CACHE[chat.id]
    except KeyError:
        chat_admins = await context.bot.get_chat_administrators(chat.id)
        admin_list = [x.user.id for x in chat_admins]
        try:
            ADMIN_CACHE[chat.id] = admin_list
        except KeyError:
            pass
        return user_id in admin_list


def is_bot_admin(chat: Chat, bot_id: int, bot_member: ChatMember = None) -> bool:
    if chat.type == "private" or chat.all_members_are_administrators:
        return True

    if not bot_member:
        return False

    return bot_member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)


async def can_delete(chat: Chat, bot_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    member = await context.bot.get_chat_member(chat.id, bot_id)
    return member.can_delete_messages


def is_user_ban_protected(update: Update, user_id: int, member: ChatMember = None) -> bool:
    chat = update.effective_chat
    msg = update.effective_message
    if (
            chat.type == "private"
            or user_id in SUDO_USERS
            or user_id in DEV_USERS
            or user_id in WHITELIST_USERS
            or user_id in SARDEGNA_USERS
            or chat.all_members_are_administrators
            or (msg and msg.reply_to_message and msg.reply_to_message.sender_chat is not None
                and msg.reply_to_message.sender_chat.type != "channel")
    ):
        return True

    if not member:
        return False

    return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)


def is_user_in_chat(chat: Chat, user_id: int) -> bool:
    return False


def _make_privilege_check(check_fn, error_msg):
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user = update.effective_user
            if user and check_fn(update.effective_chat, user.id):
                return await func(update, context, *args, **kwargs)
            elif not user:
                pass
            elif DEL_CMDS and " " not in update.effective_message.text:
                with contextlib.suppress(TelegramError):
                    await update.effective_message.delete()
            else:
                await update.effective_message.reply_text(error_msg)
        return wrapper
    return decorator


def dev_plus(func):
    return _make_privilege_check(
        lambda chat, uid: uid in DEV_USERS,
        "This is a developer restricted command. You do not have permissions to run this."
    )(func)


def sudo_plus(func):
    return _make_privilege_check(
        is_sudo_plus,
        "Who dis non-admin telling me what to do?"
    )(func)


def support_plus(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        chat = update.effective_chat
        if user and is_support_plus(chat, user.id):
            return await func(update, context, *args, **kwargs)
        elif DEL_CMDS and " " not in update.effective_message.text:
            with contextlib.suppress(TelegramError):
                await update.effective_message.delete()
    return wrapper


def whitelist_plus(func):
    return _make_privilege_check(
        is_whitelist_plus,
        "You don't have access to use this.\nVisit @YorkTownEagleUnion"
    )(func)


def user_admin(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if user and is_user_admin(update, user.id):
            return await func(update, context, *args, **kwargs)
        elif not user:
            pass
        elif DEL_CMDS and " " not in update.effective_message.text:
            with contextlib.suppress(TelegramError):
                await update.effective_message.delete()
        else:
            await update.effective_message.reply_text(
                "Who dis non-admin telling me what to do?"
            )
    return wrapper


def is_user_admin_callback_query(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.callback_query.from_user
        chat = update.effective_chat
        member = await chat.get_member(user.id)

        if member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            return await func(update, context, *args, **kwargs)

        if user.id in DEV_USERS:
            return await func(update, context, *args, **kwargs)
        elif not user:
            pass
        else:
            await update.callback_query.answer("You don't have access to use this.")
    return wrapper


def user_admin_no_reply(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if user and is_user_admin(update, user.id):
            return await func(update, context, *args, **kwargs)
        elif not user:
            pass
        elif DEL_CMDS and " " not in update.effective_message.text:
            with contextlib.suppress(TelegramError):
                await update.effective_message.delete()
    return wrapper


def user_not_admin(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        message = update.effective_message
        user = update.effective_user

        if message.is_automatic_forward:
            return
        if message.sender_chat and message.sender_chat.type != "channel":
            return
        elif user and not is_user_admin(update, user.id):
            return await func(update, context, *args, **kwargs)
        elif not user:
            pass
    return wrapper


def bot_admin(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        bot = context.bot
        chat = update.effective_chat
        update_chat_title = chat.title
        message_chat_title = update.effective_message.chat.title

        if update_chat_title == message_chat_title:
            not_admin = "I'm not admin! - REEEEEE"
        else:
            not_admin = f"I'm not admin in <b>{update_chat_title}</b>! - REEEEEE"

        bot_member = await context.bot.get_chat_member(chat.id, bot.id)
        if is_bot_admin(chat, bot.id, bot_member):
            return await func(update, context, *args, **kwargs)
        else:
            await update.effective_message.reply_text(not_admin, parse_mode=ParseMode.HTML)
    return wrapper


def bot_can_delete(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        bot = context.bot
        chat = update.effective_chat
        update_chat_title = chat.title
        message_chat_title = update.effective_message.chat.title

        if update_chat_title == message_chat_title:
            cant_delete = "I can't delete messages here!\nMake sure I'm admin and can delete other user's messages."
        else:
            cant_delete = f"I can't delete messages in <b>{update_chat_title}</b>!\nMake sure I'm admin and can delete other user's messages there."

        if await can_delete(chat, bot.id, context):
            return await func(update, context, *args, **kwargs)
        else:
            await update.effective_message.reply_text(cant_delete, parse_mode=ParseMode.HTML)
    return wrapper


async def _check_bot_permission(context, chat, attr_name):
    member = await context.bot.get_chat_member(chat.id, context.bot.id)
    return getattr(member, attr_name, False)


def can_pin(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        chat = update.effective_chat
        update_chat_title = chat.title
        message_chat_title = update.effective_message.chat.title

        if update_chat_title == message_chat_title:
            cant_pin = "I can't pin messages here!\nMake sure I'm admin and can pin messages."
        else:
            cant_pin = f"I can't pin messages in <b>{update_chat_title}</b>!\nMake sure I'm admin and can pin messages there."

        if await _check_bot_permission(context, chat, "can_pin_messages"):
            return await func(update, context, *args, **kwargs)
        else:
            await update.effective_message.reply_text(cant_pin, parse_mode=ParseMode.HTML)
    return wrapper


def can_promote(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        chat = update.effective_chat
        update_chat_title = chat.title
        message_chat_title = update.effective_message.chat.title

        if update_chat_title == message_chat_title:
            cant_promote = "I can't promote/demote people here!\nMake sure I'm admin and can appoint new admins."
        else:
            cant_promote = (
                f"I can't promote/demote people in <b>{update_chat_title}</b>!\n"
                f"Make sure I'm admin there and can appoint new admins."
            )

        if await _check_bot_permission(context, chat, "can_promote_members"):
            return await func(update, context, *args, **kwargs)
        else:
            await update.effective_message.reply_text(cant_promote, parse_mode=ParseMode.HTML)
    return wrapper


def can_restrict(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        chat = update.effective_chat
        update_chat_title = chat.title
        message_chat_title = update.effective_message.chat.title

        if update_chat_title == message_chat_title:
            cant_restrict = "I can't restrict people here!\nMake sure I'm admin and can restrict users."
        else:
            cant_restrict = f"I can't restrict people in <b>{update_chat_title}</b>!\nMake sure I'm admin there and can restrict users."

        if await _check_bot_permission(context, chat, "can_restrict_members"):
            return await func(update, context, *args, **kwargs)
        else:
            await update.effective_message.reply_text(cant_restrict, parse_mode=ParseMode.HTML)
    return wrapper


def user_can_ban(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user.id
        member = await update.effective_chat.get_member(user)

        if (
                not (member.can_restrict_members or member.status == "creator")
                and user not in SUDO_USERS
        ):
            await update.effective_message.reply_text(
                "Sorry son, but you're not worthy to wield the banhammer."
            )
            return ""

        return await func(update, context, *args, **kwargs)
    return wrapper


def connection_status(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        conn = await connected(
            context.bot,
            update,
            update.effective_chat,
            update.effective_user.id,
            need_admin=False,
        )

        if conn:
            chat = await context.bot.get_chat(conn)
            update.__setattr__("_effective_chat", chat)
            return await func(update, context, *args, **kwargs)
        else:
            if update.effective_message.chat.type == "private":
                await update.effective_message.reply_text(
                    "Send /connect in a group that you and I have in common first."
                )
                return None

            return await func(update, context, *args, **kwargs)
    return wrapper


from tg_bot.modules import connection

connected = connection.connected
