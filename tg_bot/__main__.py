import asyncio
import importlib
import logging
import re
from typing import Optional

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ApplicationHandlerStop, ContextTypes, filters
from telegram.helpers import escape_markdown

import tg_bot
from tg_bot import (
    KInit,
    TOKEN,
    WEBHOOK,
    OWNER_ID,
    CERT_PATH,
    PORT,
    URL,
    KigyoINIT,
    log,
)
from tg_bot.modules import ALL_MODULES
from tg_bot.modules.helper_funcs.chat_status import is_user_admin
from tg_bot.modules.helper_funcs.decorators import (
    kigcmd,
    kigcallback,
    kigmsg,
    rate_limit,
)
from tg_bot.modules.helper_funcs.misc import paginate_modules
from tg_bot.modules.language import gs

IMPORTED = {}
MIGRATEABLE = []
HELPABLE = {}
STATS = []
USER_INFO = []
DATA_IMPORT = []
DATA_EXPORT = []

CHAT_SETTINGS = {}
USER_SETTINGS = {}

for module_name in ALL_MODULES:
    imported_module = importlib.import_module("tg_bot.modules." + module_name)
    if not hasattr(imported_module, "__mod_name__"):
        imported_module.__mod_name__ = imported_module.__name__

    if imported_module.__mod_name__.lower() not in IMPORTED:
        IMPORTED[imported_module.__mod_name__.lower()] = imported_module
    else:
        raise Exception("Can't have two modules with the same name! Please change one")

    if hasattr(imported_module, "get_help") and imported_module.get_help:
        HELPABLE[imported_module.__mod_name__.lower()] = imported_module

    if hasattr(imported_module, "__migrate__"):
        MIGRATEABLE.append(imported_module)

    if hasattr(imported_module, "__stats__"):
        STATS.append(imported_module)

    if hasattr(imported_module, "__user_info__"):
        USER_INFO.append(imported_module)

    if hasattr(imported_module, "__import_data__"):
        DATA_IMPORT.append(imported_module)

    if hasattr(imported_module, "__export_data__"):
        DATA_EXPORT.append(imported_module)

    if hasattr(imported_module, "__chat_settings__"):
        CHAT_SETTINGS[imported_module.__mod_name__.lower()] = imported_module

    if hasattr(imported_module, "__user_settings__"):
        USER_SETTINGS[imported_module.__mod_name__.lower()] = imported_module


async def send_help(chat_id, text, keyboard=None):
    if not keyboard:
        kb = paginate_modules(0, HELPABLE, "help")
        keyboard = InlineKeyboardMarkup(kb)
    await tg_bot.application.bot.send_message(
        chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard
    )


@kigcmd(command="text")
async def test(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("This person edited a message")
    print(update.effective_message)


@kigcallback(pattern=r"start_back")
@kigcmd(command="start")
@rate_limit(40, 60)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    args = context.args

    if hasattr(update, "callback_query"):
        query = update.callback_query
        if hasattr(query, "id"):
            first_name = update.effective_user.first_name
            await update.effective_message.edit_text(
                text=gs(chat.id, "pm_start_text").format(
                    escape_markdown(first_name),
                    escape_markdown(context.bot.first_name),
                    OWNER_ID,
                ),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text=gs(chat.id, "support_chat_link_btn"),
                                url="https://t.me/YorktownEagleUnion",
                            ),
                            InlineKeyboardButton(
                                text=gs(chat.id, "updates_channel_link_btn"),
                                url="https://t.me/KigyoUpdates",
                            ),
                            InlineKeyboardButton(
                                text=gs(chat.id, "src_btn"),
                                url="https://github.com/AnimeKaizoku/EnterpriseALRobot/",
                            ),
                        ],
                        [
                            InlineKeyboardButton(
                                text="Try inline",
                                switch_inline_query_current_chat="",
                            ),
                            InlineKeyboardButton(
                                text="Help",
                                callback_data="help_back",
                            ),
                            InlineKeyboardButton(
                                text=gs(chat.id, "add_bot_to_group_btn"),
                                url="t.me/{}?startgroup=true".format(
                                    context.bot.username
                                ),
                            ),
                        ],
                    ]
                ),
            )

            await context.bot.answer_callback_query(query.id)
            return

    if update.effective_chat.type == "private":
        if args and len(args) >= 1:
            if args[0].lower() == "help":
                await send_help(update.effective_chat.id, (gs(chat.id, "pm_help_text")))
            elif args[0].lower().startswith("ghelp_"):
                query = update.callback_query
                mod = args[0].lower().split("_", 1)[1]
                if not HELPABLE.get(mod, False):
                    return
                help_list = HELPABLE[mod].get_help(chat.id)
                help_text = []
                help_buttons = []
                if isinstance(help_list, list):
                    help_text = help_list[0]
                    help_buttons = help_list[1:]
                elif isinstance(help_list, str):
                    help_text = help_list
                text = (
                    "Here is the help for the *{}* module:\n".format(
                        HELPABLE[mod].__mod_name__
                    )
                    + help_text
                )
                help_buttons.append(
                    [
                        InlineKeyboardButton(text="Back", callback_data="help_back"),
                        InlineKeyboardButton(
                            text="Support", url="https://t.me/YorkTownEagleUnion"
                        ),
                    ]
                )
                await send_help(
                    chat.id,
                    text,
                    InlineKeyboardMarkup(help_buttons),
                )

                if hasattr(query, "id"):
                    await context.bot.answer_callback_query(query.id)
            elif args[0].lower() == "markdownhelp":
                await IMPORTED["extras"].markdown_help_sender(update)
            elif args[0].lower() == "nations":
                await IMPORTED["nations"].send_nations(update)
            elif args[0].lower().startswith("stngs_"):
                match = re.match("stngs_(.*)", args[0].lower())
                chat = await context.bot.get_chat(match.group(1))

                if is_user_admin(update, update.effective_user.id):
                    await send_settings(match.group(1), update.effective_user.id, False)
                else:
                    await send_settings(match.group(1), update.effective_user.id, True)

            elif args[0][1:].isdigit() and "rules" in IMPORTED:
                await IMPORTED["rules"].send_rules(update, args[0], from_pm=True)

        else:
            first_name = update.effective_user.first_name
            await update.effective_message.reply_text(
                text=gs(chat.id, "pm_start_text").format(
                    escape_markdown(first_name),
                    escape_markdown(context.bot.first_name),
                    OWNER_ID,
                ),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text=gs(chat.id, "support_chat_link_btn"),
                                url="https://t.me/YorktownEagleUnion",
                            ),
                            InlineKeyboardButton(
                                text=gs(chat.id, "updates_channel_link_btn"),
                                url="https://t.me/KigyoUpdates",
                            ),
                            InlineKeyboardButton(
                                text=gs(chat.id, "src_btn"),
                                url="https://github.com/Dank-del/EnterpriseALRobot",
                            ),
                        ],
                        [
                            InlineKeyboardButton(
                                text="Try inline",
                                switch_inline_query_current_chat="",
                            ),
                            InlineKeyboardButton(
                                text="Help",
                                callback_data="help_back",
                            ),
                            InlineKeyboardButton(
                                text=gs(chat.id, "add_bot_to_group_btn"),
                                url="t.me/{}?startgroup=true".format(
                                    context.bot.username
                                ),
                            ),
                        ],
                    ]
                ),
            )

    else:
        await update.effective_message.reply_text(gs(chat.id, "grp_start_text"))

    if hasattr(update, "callback_query"):
        query = update.callback_query
        if hasattr(query, "id"):
            await context.bot.answer_callback_query(query.id)


async def error_callback(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.exception(
        "Unhandled exception while processing update %s",
        update,
        exc_info=context.error,
    )


@kigcallback(pattern=r"help_")
@rate_limit(40, 60)
async def help_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    mod_match = re.match(r"help_module\((.+?)\)", query.data)
    prev_match = re.match(r"help_prev\((.+?)\)", query.data)
    next_match = re.match(r"help_next\((.+?)\)", query.data)
    back_match = re.match(r"help_back", query.data)
    chat = update.effective_chat

    try:
        if mod_match:
            module = mod_match.group(1)
            module = module.replace("_", " ")
            help_list = HELPABLE[module].get_help(update.effective_chat.id)
            if isinstance(help_list, list):
                help_text = help_list[0]
                help_buttons = help_list[1:]
            elif isinstance(help_list, str):
                help_text = help_list
                help_buttons = []
            text = (
                "Here is the help for the *{}* module:\n".format(
                    HELPABLE[module].__mod_name__
                )
                + help_text
            )
            help_buttons.append(
                [
                    InlineKeyboardButton(text="Back", callback_data="help_back"),
                    InlineKeyboardButton(
                        text="Support", url="https://t.me/YorkTownEagleUnion"
                    ),
                ]
            )
            await query.message.edit_text(
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(help_buttons),
            )

        elif prev_match:
            curr_page = int(prev_match.group(1))
            kb = paginate_modules(curr_page - 1, HELPABLE, "help")
            await query.message.edit_text(
                text=gs(chat.id, "pm_help_text"),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(kb),
            )

        elif next_match:
            next_page = int(next_match.group(1))
            kb = paginate_modules(next_page + 1, HELPABLE, "help")
            await query.message.edit_text(
                text=gs(chat.id, "pm_help_text"),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(kb),
            )

        elif back_match:
            kb = paginate_modules(0, HELPABLE, "help")
            await query.message.edit_text(
                text=gs(chat.id, "pm_help_text"),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(kb),
            )

        await context.bot.answer_callback_query(query.id)

    except BadRequest:
        pass


@kigcmd(command="help")
@rate_limit(40, 60)
async def get_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    args = update.effective_message.text.split(None, 1)

    if chat.type != chat.PRIVATE:
        if len(args) >= 2:
            if any(args[1].lower() == x for x in HELPABLE):
                module = args[1].lower()
                await update.effective_message.reply_text(
                    f"Contact me in PM to get help of {module.capitalize()}",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    text="Help",
                                    url="t.me/{}?start=ghelp_{}".format(
                                        context.bot.username, module
                                    ),
                                )
                            ]
                        ]
                    ),
                )
            else:
                await update.effective_message.reply_text(
                    f"<code>{args[1].lower()}</code> is not a module",
                    parse_mode=ParseMode.HTML,
                )
            return

        await update.effective_message.reply_text(
            "Contact me in PM to get the list of possible commands.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="Help",
                            url="t.me/{}?start=help".format(context.bot.username),
                        )
                    ]
                ]
            ),
        )
        return

    if len(args) >= 2:
        if any(args[1].lower() == x for x in HELPABLE):
            module = args[1].lower()
            help_list = HELPABLE[module].get_help(chat.id)
            help_text = []
            help_buttons = []
            if isinstance(help_list, list):
                help_text = help_list[0]
                help_buttons = help_list[1:]
            elif isinstance(help_list, str):
                help_text = help_list
            text = (
                "Here is the available help for the *{}* module:\n".format(
                    HELPABLE[module].__mod_name__
                )
                + help_text
            )
            help_buttons.append(
                [
                    InlineKeyboardButton(text="Back", callback_data="help_back"),
                    InlineKeyboardButton(
                        text="Support", url="https://t.me/YorkTownEagleUnion"
                    ),
                ]
            )
            await send_help(
                chat.id,
                text,
                InlineKeyboardMarkup(help_buttons),
            )
        else:
            await update.effective_message.reply_text(
                f"<code>{args[1].lower()}</code> is not a module",
                parse_mode=ParseMode.HTML,
            )
    else:
        await send_help(chat.id, (gs(chat.id, "pm_help_text")))


async def send_settings(chat_id: int, user_id: int, user=False):
    bot = tg_bot.application.bot
    if user:
        if USER_SETTINGS:
            settings = "\n\n".join(
                "*{}*:\n{}".format(mod.__mod_name__, mod.__user_settings__(user_id))
                for mod in USER_SETTINGS.values()
            )
            await bot.send_message(
                user_id,
                "These are your current settings:" + "\n\n" + settings,
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await bot.send_message(
                user_id,
                "Seems like there aren't any user specific settings available :'(",
                parse_mode=ParseMode.MARKDOWN,
            )
    elif CHAT_SETTINGS:
        chat_name = (await bot.get_chat(chat_id)).title
        await bot.send_message(
            user_id,
            text="Which module would you like to check {}'s settings for?".format(
                chat_name
            ),
            reply_markup=InlineKeyboardMarkup(
                paginate_modules(0, CHAT_SETTINGS, "stngs", chat=chat_id)
            ),
        )
    else:
        await bot.send_message(
            user_id,
            "Seems like there aren't any chat settings available :'(\nSend this "
            "in a group chat you're admin in to find its current settings!",
            parse_mode=ParseMode.MARKDOWN,
        )


@kigcallback(pattern=r"stngs_")
@rate_limit(40, 60)
async def settings_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    bot = context.bot
    mod_match = re.match(r"stngs_module\((.+?),(.+?)\)", query.data)
    prev_match = re.match(r"stngs_prev\((.+?),(.+?)\)", query.data)
    next_match = re.match(r"stngs_next\((.+?),(.+?)\)", query.data)
    back_match = re.match(r"stngs_back\((.+?)\)", query.data)
    try:
        if mod_match:
            chat_id = mod_match.group(1)
            module = mod_match.group(2)
            chat = await bot.get_chat(chat_id)
            text = "*{}* has the following settings for the *{}* module:\n\n".format(
                escape_markdown(chat.title), CHAT_SETTINGS[module].__mod_name__
            ) + CHAT_SETTINGS[module].__chat_settings__(chat_id, user.id)
            await query.message.reply_text(
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text="Back",
                                callback_data="stngs_back({})".format(chat_id),
                            )
                        ]
                    ]
                ),
            )

        elif prev_match:
            chat_id = prev_match.group(1)
            curr_page = int(prev_match.group(2))
            chat = await bot.get_chat(chat_id)
            await query.message.reply_text(
                "Hi there! There are quite a few settings for {} - go ahead and pick what "
                "you're interested in.".format(chat.title),
                reply_markup=InlineKeyboardMarkup(
                    paginate_modules(
                        curr_page - 1, CHAT_SETTINGS, "stngs", chat=chat_id
                    )
                ),
            )

        elif next_match:
            chat_id = next_match.group(1)
            next_page = int(next_match.group(2))
            chat = await bot.get_chat(chat_id)
            await query.message.reply_text(
                "Hi there! There are quite a few settings for {} - go ahead and pick what "
                "you're interested in.".format(chat.title),
                reply_markup=InlineKeyboardMarkup(
                    paginate_modules(
                        next_page + 1, CHAT_SETTINGS, "stngs", chat=chat_id
                    )
                ),
            )

        elif back_match:
            chat_id = back_match.group(1)
            chat = await bot.get_chat(chat_id)
            await query.message.reply_text(
                text="Hi there! There are quite a few settings for {} - go ahead and pick what "
                "you're interested in.".format(escape_markdown(chat.title)),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(
                    paginate_modules(0, CHAT_SETTINGS, "stngs", chat=chat_id)
                ),
            )

        await bot.answer_callback_query(query.id)
        await query.message.delete()
    except BadRequest as excp:
        if excp.message not in [
            "Message is not modified",
            "Query_id_invalid",
            "Message can't be deleted",
        ]:
            logging.exception("Exception in settings buttons. %s", str(query.data))


@kigcmd(command="settings")
@rate_limit(40, 60)
async def get_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    if chat.type == chat.PRIVATE:
        await send_settings(chat.id, user.id, True)

    elif is_user_admin(update, user.id):
        text = "Click here to get this chat's settings, as well as yours."
        await msg.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="Settings",
                            url="t.me/{}?start=stngs_{}".format(
                                context.bot.username, chat.id
                            ),
                        )
                    ]
                ]
            ),
        )
    else:
        text = "Click here to check your settings."


@kigcmd(command="donate")
@rate_limit(40, 60)
async def donate(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("I'm free for everyone! >_<")


@kigmsg(filters.StatusUpdate.MIGRATE)
@rate_limit(40, 60)
async def migrate_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if msg.migrate_to_chat_id:
        old_chat = update.effective_chat.id
        new_chat = msg.migrate_to_chat_id
    elif msg.migrate_from_chat_id:
        old_chat = msg.migrate_from_chat_id
        new_chat = update.effective_chat.id
    else:
        return

    logging.info("Migrating from %s, to %s", str(old_chat), str(new_chat))
    for mod in MIGRATEABLE:
        mod.__migrate__(old_chat, new_chat)

    logging.info("Successfully migrated!")
    raise ApplicationHandlerStop


async def _post_init(app):
    from tg_bot.modules.sql.users_sql import ensure_bot_in_db
    await asyncio.get_running_loop().run_in_executor(None, ensure_bot_in_db)


async def _post_shutdown(app):
    from tg_bot.http_client import http
    from tg_bot import redis_client, redis_pool
    try:
        await http.aclose()
    except Exception:
        log.exception("Failed to close httpx client")
    try:
        await redis_client.aclose()
    except Exception:
        log.exception("Failed to close redis client")
    try:
        await redis_pool.disconnect()
    except Exception:
        log.exception("Failed to disconnect redis pool")


def main():
    from telegram.ext import Application
    from tg_bot.modules.helper_funcs.decorators import kigyo_handler

    app = (
        Application.builder()
        .token(TOKEN)
        .base_url(KInit.BOT_API_URL)
        .base_file_url(KInit.BOT_API_FILE_URL)
        .read_timeout(10)
        .connect_timeout(10)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )

    tg_bot.application = app

    kigyo_handler.register_all(app)
    app.add_error_handler(error_callback)

    logging.info("[KIGYO] Successfully loaded modules: " + str(ALL_MODULES))

    if WEBHOOK:
        logging.info("Using webhooks.")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            allowed_updates=Update.ALL_TYPES,
            webhook_url=URL + TOKEN,
            drop_pending_updates=KInit.DROP_UPDATES,
            cert=CERT_PATH if CERT_PATH else None,
        )
    else:
        logging.info("Kigyo started, Using long polling.")
        KigyoINIT.bot_id = 0
        KigyoINIT.bot_username = KInit.bot_username
        KigyoINIT.bot_name = KInit.bot_name
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=KInit.DROP_UPDATES,
        )


if __name__ == "__main__":
    main()
