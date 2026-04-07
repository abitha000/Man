import requests
from telegram.constants import ParseMode
from telegram import Update
from telegram.ext import ContextTypes
from tg_bot.modules.helper_funcs.decorators import kigcmd, rate_limit

@kigcmd(command=["ud", "urban"])
@rate_limit(40, 60)
async def ud(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    text = message.text[len("/ud ") :]
    results = requests.get(
        f"https://api.urbandictionary.com/v0/define?term={text}"
    ).json()
    try:
        reply_text = f'*{text}*\n\n{results["list"][0]["definition"]}\n\n_{results["list"][0]["example"]}_'
    except Exception:
        reply_text = "No results found."
    await message.reply_text(reply_text, parse_mode=ParseMode.MARKDOWN)
