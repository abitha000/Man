from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from tg_bot.modules.helper_funcs.chat_status import dev_plus
from tg_bot.modules.helper_funcs.decorators import kigyo_handler

DEBUG_MODE = False


@dev_plus
async def debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global DEBUG_MODE
    args = update.effective_message.text.split(None, 1)
    message = update.effective_message
    print(DEBUG_MODE)
    if len(args) > 1:
        if args[1] in ("yes", "on"):
            DEBUG_MODE = True
            await message.reply_text("Debug mode is now on.")
        elif args[1] in ("no", "off"):
            DEBUG_MODE = False
            await message.reply_text("Debug mode is now off.")
    elif DEBUG_MODE:
        await message.reply_text("Debug mode is currently on.")
    else:
        await message.reply_text("Debug mode is currently off.")


DEBUG_HANDLER = CommandHandler("debug", debug)
kigyo_handler._add_handler(DEBUG_HANDLER)

__mod_name__ = "Debug"
__command_list__ = ["debug"]
__handlers__ = [DEBUG_HANDLER]
