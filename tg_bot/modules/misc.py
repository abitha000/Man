import contextlib
import html
import time
import git
import requests
from io import BytesIO
from telegram import Chat, Update, MessageEntity, User
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes, filters
from telegram.helpers import mention_html, escape_markdown
from subprocess import Popen, PIPE

from tg_bot import (
    OWNER_ID,
    SUDO_USERS,
    SUPPORT_USERS,
    DEV_USERS,
    SARDEGNA_USERS,
    WHITELIST_USERS,
    INFOPIC,
    StartTime
)
from tg_bot.__main__ import STATS, USER_INFO, TOKEN
from tg_bot.modules.sql import SESSION
from tg_bot.modules.helper_funcs.chat_status import user_admin, sudo_plus
from tg_bot.modules.helper_funcs.extraction import extract_user
import tg_bot.modules.sql.users_sql as sql
from tg_bot.modules.users import __user_info__ as chat_count
from tg_bot.modules.language import gs
from telegram import __version__ as ptbver, InlineKeyboardMarkup, InlineKeyboardButton
from psutil import cpu_percent, virtual_memory, disk_usage, boot_time
import datetime
import platform
from platform import python_version
from tg_bot.modules.helper_funcs.decorators import kigcmd, kigcallback, rate_limit

MARKDOWN_HELP = """
Markdown is a very powerful formatting tool supported by telegram. This bot has some enhancements, to make sure that \
saved messages are correctly parsed, and to allow you to create buttons.

- <code>_italic_</code>: wrapping text with '_' will produce italic text
- <code>*bold*</code>: wrapping text with '*' will produce bold text
- <code>`code`</code>: wrapping text with '`' will produce monospaced text, also known as 'code'
- <code>[sometext](someURL)</code>: this will create a link - the message will just show <code>sometext</code>, \
and tapping on it will open the page at <code>someURL</code>.
EG: <code>[test](example.com)</code>

- <code>[buttontext](buttonurl:someURL)</code>: this is a special enhancement to allow users to have telegram \
buttons in their markdown. <code>buttontext</code> will be what is displayed on the button, and <code>someurl</code> \
will be the url which is opened.
EG: <code>[This is a button](buttonurl:example.com)</code>

If you want multiple buttons on the same line, use :same, as such:
<code>[one](buttonurl://example.com)
[two](buttonurl://google.com:same)</code>
This will create two buttons on a single line, instead of one button per line.

Keep in mind that your message <b>MUST</b> contain some text other than just a button!
"""

@kigcmd(command='id')
@rate_limit(40, 60)
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot, args = context.bot, context.args
    message = update.effective_message
    chat = update.effective_chat
    msg = update.effective_message
    if user_id := await extract_user(msg, args):
        if msg.reply_to_message and msg.reply_to_message.forward_from:

            user1 = message.reply_to_message.from_user
            user2 = message.reply_to_message.forward_from

            await msg.reply_text(
                f"<b>Telegram ID:</b>,"
                f"• {html.escape(user2.first_name)} - <code>{user2.id}</code>.\n"
                f"• {html.escape(user1.first_name)} - <code>{user1.id}</code>.",
                parse_mode=ParseMode.HTML,
            )

        else:

            user = await bot.get_chat(user_id)
            await msg.reply_text(
                f"{html.escape(user.first_name)}'s id is <code>{user.id}</code>.",
                parse_mode=ParseMode.HTML,
            )

    elif chat.type == "private":
        await msg.reply_text(
            f"Your id is <code>{chat.id}</code>.", parse_mode=ParseMode.HTML
        )

    else:
        await msg.reply_text(
            f"This group's id is <code>{chat.id}</code>.", parse_mode=ParseMode.HTML
        )

@kigcmd(command='gifid')
@rate_limit(40, 60)
async def gifid(update: Update, _):
    msg = update.effective_message
    if msg.reply_to_message and msg.reply_to_message.animation:
        await update.effective_message.reply_text(
            f"Gif ID:\n<code>{msg.reply_to_message.animation.file_id}</code>",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.effective_message.reply_text("Please reply to a gif to get its ID.")

@kigcmd(command='info')
@rate_limit(40, 60)
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    args = context.args
    message = update.effective_message
    chat = update.effective_chat
    if user_id := await extract_user(update.effective_message, args):
        user = await bot.get_chat(user_id)

    elif not message.reply_to_message and not args:
        user = (
            message.sender_chat
            if message.sender_chat is not None
            else message.from_user
        )

    elif not message.reply_to_message and (
        not args
        or (
            len(args) >= 1
            and not args[0].startswith("@")
            and not args[0].lstrip("-").isdigit()
            and not message.parse_entities([MessageEntity.TEXT_MENTION])
        )
    ):
        await message.reply_text("I can't extract a user from this.")
        return

    else:
        return

    if hasattr(user, 'type') and user.type != "private":
        text = get_chat_info(user)
        is_chat = True
    else:
        text = await get_user_info(chat, user, context)
        is_chat = False

    if INFOPIC:
        if is_chat:
            try:
                pic = user.photo.big_file_id
                pfp = await bot.get_file(pic)
                pfp_data = BytesIO()
                await pfp.download_to_memory(pfp_data)
                pfp_data.seek(0)
                await message.reply_document(
                        document=pfp_data,
                        filename=f'{user.id}.jpg',
                        caption=text,
                        parse_mode=ParseMode.HTML,
                )
            except AttributeError:
                await message.reply_text(
                        text,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True,
                )
        else:
            try:
                profile = (await bot.get_user_profile_photos(user.id)).photos[0][-1]
                _file = await bot.get_file(profile["file_id"])

                _file_data = BytesIO()
                await _file.download_to_memory(_file_data)
                _file_data.seek(0)

                await message.reply_document(
                        document=_file_data,
                        caption=(text),
                        parse_mode=ParseMode.HTML,
                )

            except IndexError:
                await message.reply_text(
                        text, parse_mode=ParseMode.HTML, disable_web_page_preview=True
                )

    else:
        await message.reply_text(
            text, parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )


async def get_user_info(chat: Chat, user: User, context: ContextTypes.DEFAULT_TYPE) -> str:
    bot = context.bot
    text = (
        f"<b>General:</b>\n"
        f"ID: <code>{user.id}</code>\n"
        f"First Name: {html.escape(user.first_name)}"
    )
    if user.last_name:
        text += f"\nLast Name: {html.escape(user.last_name)}"
    if user.username:
        text += f"\nUsername: @{html.escape(user.username)}"
    text += f"\nPermanent user link: {mention_html(user.id, 'link')}"
    Nation_level_present = False
    num_chats = sql.get_user_num_chats(user.id)
    text += f"\n<b>Chat count</b>: <code>{num_chats}</code>"
    with contextlib.suppress(BadRequest):
        user_member = await chat.get_member(user.id)
        if user_member.status == "administrator":
            result = await bot.get_chat_member(chat.id, user.id)
            if result.custom_title:
                text += f"\nThis user holds the title <b>{result.custom_title}</b> here."
    if user.id == OWNER_ID:
        text += '\nThis person is my owner'
        Nation_level_present = True
    elif user.id in DEV_USERS:
        text += '\nThis Person is a part of Eagle Union'
        Nation_level_present = True
    elif user.id in SUDO_USERS:
        text += '\nThe Nation level of this person is Royal'
        Nation_level_present = True
    elif user.id in SUPPORT_USERS:
        text += '\nThe Nation level of this person is Sakura'
        Nation_level_present = True
    elif user.id in SARDEGNA_USERS:
        text += '\nThe Nation level of this person is Sardegna'
        Nation_level_present = True
    elif user.id in WHITELIST_USERS:
        text += '\nThe Nation level of this person is Neptunia'
        Nation_level_present = True
    if Nation_level_present:
        text += f' [<a href="https://t.me/{bot.username}?start=nations">?</a>]'
    text += "\n"
    for mod in USER_INFO:
        if mod.__mod_name__ == "Users":
            continue

        try:
            mod_info = mod.__user_info__(user.id)
        except TypeError:
            mod_info = mod.__user_info__(user.id, chat.id)
        if mod_info:
            text += "\n" + mod_info
    return text


def get_chat_info(user):
    text = (
        f"<b>Chat Info:</b>\n"
        f"<b>Title:</b> {user.title}"
    )
    if user.username:
        text += f"\n<b>Username:</b> @{html.escape(user.username)}"
    text += f"\n<b>Chat ID:</b> <code>{user.id}</code>"
    text += f"\n<b>Chat Type:</b> {user.type.capitalize()}"
    text += "\n" + chat_count(user.id)

    return text


@kigcmd(command='echo', cmd_filter=filters.ChatType.GROUPS)
@user_admin
@rate_limit(40, 60)
async def echo(update: Update, _):
    args = update.effective_message.text.split(None, 1)
    message = update.effective_message

    if message.reply_to_message:
        await message.reply_to_message.reply_text(args[1])
    else:
        await message.reply_text(args[1], quote=False)

    await message.delete()


def shell(command):
    process = Popen(command, stdout=PIPE, shell=True, stderr=PIPE)
    stdout, stderr = process.communicate()
    return (stdout, stderr)

@kigcmd(command='markdownhelp', cmd_filter=filters.ChatType.PRIVATE)
@rate_limit(40, 60)
async def markdown_help(update: Update, _):
    chat = update.effective_chat
    await update.effective_message.reply_text((gs(chat.id, "markdown_help_text")), parse_mode=ParseMode.HTML)
    await update.effective_message.reply_text(
        "Try forwarding the following message to me, and you'll see!"
    )
    await update.effective_message.reply_text(
        "/save test This is a markdown test. _italics_, *bold*, `code`, "
        "[URL](example.com) [button](buttonurl:github.com) "
        "[button2](buttonurl://google.com:same)"
    )

def get_readable_time(seconds: int) -> str:
    count = 0
    ping_time = ""
    time_list = []
    time_suffix_list = ["s", "m", "h", "days"]

    while count < 4:
        count += 1
        remainder, result = divmod(seconds, 60) if count < 3 else divmod(seconds, 24)
        if seconds == 0 and remainder == 0:
            break
        time_list.append(int(result))
        seconds = int(remainder)

    for x in range(len(time_list)):
        time_list[x] = str(time_list[x]) + time_suffix_list[x]
    if len(time_list) == 4:
        ping_time += f'{time_list.pop()}, '

    time_list.reverse()
    ping_time += ":".join(time_list)

    return ping_time

stats_str = '''
'''
@kigcmd(command='stats', can_disable=False)
@sudo_plus
@rate_limit(40, 60)
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_size = SESSION.execute("SELECT pg_size_pretty(pg_database_size(current_database()))").scalar_one_or_none()
    uptime = datetime.datetime.fromtimestamp(boot_time()).strftime("%Y-%m-%d %H:%M:%S")
    botuptime = get_readable_time((time.time() - StartTime))
    status = "*\u2552\u2550\u2550\u2550\u300c System statistics: \u300d*\n\n"
    status += f"*\u2022 System Start time:* {str(uptime)}" + "\n"
    uname = platform.uname()
    status += f"*\u2022 System:* {str(uname.system)}" + "\n"
    status += f"*\u2022 Node name:* {escape_markdown(str(uname.node))}" + "\n"
    status += f"*\u2022 Release:* {escape_markdown(str(uname.release))}" + "\n"
    status += f"*\u2022 Machine:* {escape_markdown(str(uname.machine))}" + "\n"

    mem = virtual_memory()
    cpu = cpu_percent()
    disk = disk_usage("/")
    status += f"*\u2022 CPU:* {str(cpu)}" + " %\n"
    status += f"*\u2022 RAM:* {str(mem[2])}" + " %\n"
    status += f"*\u2022 Storage:* {str(disk[3])}" + " %\n\n"
    status += f"*\u2022 Python version:* {python_version()}" + "\n"
    status += f"*\u2022 python-telegram-bot:* {str(ptbver)}" + "\n"
    status += f"*\u2022 Uptime:* {str(botuptime)}" + "\n"
    status += f"*\u2022 Database size:* {str(db_size)}" + "\n"
    kb = [
          [
           InlineKeyboardButton('Ping', callback_data='pingCB')
          ]
    ]
    try:
        repo = git.Repo(search_parent_directories=True)
        sha = repo.head.object.hexsha
        status += f"*\u2022 Commit*: `{sha[:9]}`\n"
    except Exception as e:
        status += f"*\u2022 Commit*: `{str(e)}`\\n"

    try:
        await update.effective_message.reply_text(status +
            "\n*Bot statistics*:\n"
            + "\n".join([mod.__stats__() for mod in STATS]) +
            "\n\n[\u2359 GitHub](https://github.com/Dank-del/EnterpriseALRobot) | [\u235a GitLab](https://gitlab.com/Dank-del/EnterpriseALRobot)\n\n" +
            "\u2558\u2550\u2550\u300c by [Dank-del](github.com/Dank-del) \u300d\n",
        parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb), disable_web_page_preview=True)
    except Exception:
        await update.effective_message.reply_text(
            (
                (
                    (
                        "\n*Bot statistics*:\n"
                        + "\n".join(mod.__stats__() for mod in STATS)
                    )
                    + "\n\n\u2359 [GitHub](https://github.com/Dank-del/EnterpriseALRobot) | \u235a [GitLab](https://gitlab.com/Dank-del/EnterpriseALRobot)\n\n"
                )
                + "\u2558\u2550\u2550\u300c by [Dank-del](github.com/Dank-del) \u300d\n"
            ),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(kb),
            disable_web_page_preview=True,
        )

@kigcmd(command='ping')
@rate_limit(40, 60)
async def ping(update: Update, _):
    msg = update.effective_message
    start_time = time.time()
    message = await msg.reply_text("Pinging...")
    end_time = time.time()
    ping_time = round((end_time - start_time) * 1000, 3)
    await message.edit_text(
        "*Pong!!!*\n`{}ms`".format(ping_time), parse_mode=ParseMode.MARKDOWN
    )


@kigcallback(pattern=r'^pingCB')
@rate_limit(40, 60)
async def pingCallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    start_time = time.time()
    requests.get('https://api.telegram.org')
    end_time = time.time()
    ping_time = round((end_time - start_time) * 1000, 3)
    await query.answer(f'Pong! {ping_time}ms')


def get_help(chat):
    return gs(chat, "misc_help")



__mod_name__ = "Misc"
