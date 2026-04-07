import contextlib
import logging
from telegram.error import BadRequest
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CallbackQueryHandler
from typing import List
from tg_bot.modules.helper_funcs.anonymous import AdminPerms, user_admin
from tg_bot.modules.helper_funcs.chat_status import bot_admin, is_user_admin_callback_query
from tg_bot.modules.helper_funcs.decorators import rate_limit, kigcmd
from tg_bot.modules.log_channel import loggable
from pydantic import BaseModel
from uuid import uuid4
from tg_bot.modules.helper_funcs.decorators import kigyo_handler

class DeleteMessageCallback(BaseModel):
    purge_id: str
    chat_id: int
    message_ids: List[int]

DEL_MSG_CB_MAP: List[DeleteMessageCallback] = []

@is_user_admin_callback_query
@bot_admin
@rate_limit(40, 60)
@loggable
async def purge_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    message = update.effective_message
    data = query.data
    purge_id = data.split("_")[-1]
    if data == "purge_cancel":
        await message.edit_text("Purge has been cancelled.")
        return f"#PURGE_CANCELLED \n<b>Admin:</b> {query.from_user.first_name}\n<b>Chat:</b> {update.effective_chat.title}\n"

    for entry in DEL_MSG_CB_MAP:
        if entry.purge_id == purge_id:
            try:
                resp = context.bot._request.post(
                f"{context.bot.base_url}/deleteMessages",
                        {
                            "chat_id": entry.chat_id,
                            "message_ids": entry.message_ids
                        },
                )
                logging.debug(resp)
                await query.edit_message_text(text="Purge completed.")
                return f"#PURGE_COMPLETED \n<b>Admin:</b> {query.from_user.first_name}\n<b>Chat:</b> {update.effective_chat.title}\n<b>Messages:</b> {len(entry.message_ids)}\n"
            except BadRequest as e:
                if e.message == "Too many message identifiers specified":
                    for msg_id in entry.message_ids:
                        with contextlib.suppress(BadRequest):
                            await context.bot.delete_message(chat_id=entry.chat_id, message_id=msg_id)
                    await query.edit_message_text(text="Purge completed.")
                    return f"#PURGE_COMPLETED \n<b>Admin:</b> {query.from_user.first_name}\n<b>Chat:</b> {update.effective_chat.title}\n<b>Messages:</b> {len(entry.message_ids)}\n"
                await query.edit_message_text(text="Failed to purge")
                return f"#PURGE_FAILED \n<b>Admin:</b> {query.from_user.first_name}\n<b>Chat:</b> {update.effective_chat.title}\n"
    await query.edit_message_text(text="Purge failed or purge ID not found.")
    return f"#PURGE_FAILED \n<b>Admin:</b> {query.from_user.first_name}\n<b>Chat:</b> {update.effective_chat.title}\n"


@kigcmd(command='purge')
@bot_admin
@user_admin(AdminPerms.CAN_DELETE_MESSAGES)
@rate_limit(40, 60)
@loggable
async def purge_messages_botapi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    message_id_from = update.effective_message.reply_to_message.message_id if update.effective_message.reply_to_message else None
    message_id_to = update.effective_message.message_id

    if not message_id_from:
        await update.effective_message.reply_text("Reply to the message you want to start purging from.")
        return
    messages_to_delete = []
    try:
        messages_to_delete.extend(iter(range(message_id_from, message_id_to + 1)))
        entry = DeleteMessageCallback(chat_id=chat_id, message_ids=messages_to_delete, purge_id=str(uuid4()))
        DEL_MSG_CB_MAP.append(entry)
        buttons = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="Confirm",
                        callback_data=f"purge_confirm_{entry.purge_id}",
                    ),
                    InlineKeyboardButton(
                        text="Cancel", callback_data="purge_cancel"
                    ),
                ]
            ]
        )
        await update.effective_message.reply_text(
            f"Purge {len(messages_to_delete)} message(s) from {update.effective_chat.title}? This action cannot be undone.",
            reply_markup=buttons,
            parse_mode=ParseMode.MARKDOWN,
        )
        return f"#PURGE_ATTEMPT \n<b>Admin:</b> {update.effective_user.first_name} \n<b>Messages:</b> {len(messages_to_delete)}\n"
    except Exception as e:
        logging.exception(e)
        await update.effective_message.reply_text("An error occurred while purging")

from tg_bot.modules.language import gs

def get_help(chat):
    return gs(chat, "purge_help")

CALLBACK_QUERY_HANDLER = CallbackQueryHandler(purge_confirm, pattern=r"purge.*")
kigyo_handler._add_handler(CALLBACK_QUERY_HANDLER)



__mod_name__ = "Purges"
__command_list__ = ["del", "purge"]
