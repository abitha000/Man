import asyncio
import html
import os
import re
import subprocess
import sys

from tg_bot import DEV_USERS
from tg_bot.modules.helper_funcs.chat_status import dev_plus
from tg_bot.modules.helper_funcs.decorators import kigyo_handler
from telegram import TelegramError, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler


@dev_plus
async def leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    args = context.args
    if args:
        chat_id = str(args[0])
        leave_msg = " ".join(args[1:])
        try:
            await context.bot.send_message(chat_id, leave_msg)
            await bot.leave_chat(int(chat_id))
            await update.effective_message.reply_text("Left chat.")
        except TelegramError:
            await update.effective_message.reply_text("Failed to leave chat for some reason.")
    else:
        chat = update.effective_chat
        kb = [[
            InlineKeyboardButton(text="I am sure of this action.", callback_data="leavechat_cb_({})".format(chat.id))
        ]]
        await update.effective_message.reply_text("I'm going to leave {}, press the button below to confirm".format(chat.title), reply_markup=InlineKeyboardMarkup(kb))


async def leave_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    callback = update.callback_query
    if callback.from_user.id not in DEV_USERS:
        await callback.answer(text="This isn't for you", show_alert=True)
        return

    match = re.match(r"leavechat_cb_\((.+?)\)", callback.data)
    chat = int(match.group(1))
    await bot.leave_chat(chat_id=chat)
    await callback.answer(text="Left chat")

@dev_plus
async def gitpull(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sent_msg = await update.effective_message.reply_text(
        "Pulling all changes from remote and then attempting to restart."
    )
    subprocess.Popen("git pull", stdout=subprocess.PIPE, shell=True)

    sent_msg_text = sent_msg.text + "\n\nChanges pulled...I guess.. Restarting in "

    for i in reversed(range(5)):
        await sent_msg.edit_text(sent_msg_text + str(i + 1))
        await asyncio.sleep(1)

    await sent_msg.edit_text("Restarted.")

    os.system("restart.bat")
    os.execv("start.bat", sys.argv)


@dev_plus
async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "Starting a new instance and shutting down this one"
    )

    os.system("restart.bat")
    os.execv("start.bat", sys.argv)


@dev_plus
async def pip_install(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    args = context.args
    if not args:
        await message.reply_text("Enter a package name.")
        return
    if len(args) >= 1:
        cmd = "py -m pip install {}".format(' '.join(args))
        process = subprocess.Popen(
            cmd.split(" "), stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True,
        )
        stdout, stderr = process.communicate()
        reply = ""
        stderr = stderr.decode()
        stdout = stdout.decode()
        if stdout:
            reply += f"*Stdout*\n`{stdout}`\n"
        if stderr:
            reply += f"*Stderr*\n`{stderr}`\n"

        await message.reply_text(text=reply, parse_mode=ParseMode.MARKDOWN)


@dev_plus
async def get_chat_by_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    args = context.args
    if not args:
        await msg.reply_text("<i>Chat ID required</i>", parse_mode=ParseMode.HTML)
        return
    if len(args) >= 1:
        data = await context.bot.get_chat(args[0])
        m = "<b>Found chat, below are the details.</b>\n\n"
        m += "<b>Title</b>: {}\n".format(html.escape(data.title))
        m += "<b>Members</b>: {}\n\n".format(await data.get_member_count())
        if data.description:
            m += "<i>{}</i>\n\n".format(html.escape(data.description))
        if data.linked_chat_id:
            m += "<b>Linked chat</b>: {}\n".format(data.linked_chat_id)

        m += "<b>Type</b>: {}\n".format(data.type)
        if data.username:
            m += "<b>Username</b>: {}\n".format(html.escape(data.username))
        m += "<b>ID</b>: {}\n".format(data.id)
        m += "\n<b>Permissions</b>:\n <code>{}</code>\n".format(data.permissions)

        if data.invite_link:
            m += "\n<b>Invitelink</b>: {}".format(data.invite_link)

        await msg.reply_text(text=m, parse_mode=ParseMode.HTML)


PIP_INSTALL_HANDLER = CommandHandler("install", pip_install)
LEAVE_HANDLER = CommandHandler("leave", leave)
GITPULL_HANDLER = CommandHandler("gitpull", gitpull)
RESTART_HANDLER = CommandHandler("reboot", restart)
GET_CHAT_HANDLER = CommandHandler("getchat", get_chat_by_id)
LEAVE_CALLBACK = CallbackQueryHandler(
    leave_cb, pattern=r"leavechat_cb_"
)

kigyo_handler._add_handler(LEAVE_HANDLER)
kigyo_handler._add_handler(GITPULL_HANDLER)
kigyo_handler._add_handler(RESTART_HANDLER)
kigyo_handler._add_handler(PIP_INSTALL_HANDLER)
kigyo_handler._add_handler(GET_CHAT_HANDLER)
kigyo_handler._add_handler(LEAVE_CALLBACK)

__mod_name__ = "Dev"
__handlers__ = [LEAVE_HANDLER, GITPULL_HANDLER, RESTART_HANDLER, PIP_INSTALL_HANDLER, GET_CHAT_HANDLER, LEAVE_CALLBACK]
