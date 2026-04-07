from telegram.constants import ParseMode
from telegram import Update
from telegram.ext import ContextTypes
from tg_bot.modules.helper_funcs.decorators import kigcmd, rate_limit

normiefont = [
    "a",
    "b",
    "c",
    "d",
    "e",
    "f",
    "g",
    "h",
    "i",
    "j",
    "k",
    "l",
    "m",
    "n",
    "o",
    "p",
    "q",
    "r",
    "s",
    "t",
    "u",
    "v",
    "w",
    "x",
    "y",
    "z",
]
weebyfont = [
    "\u5352",
    "\u4e43",
    "\u531a",
    "\u5200",
    "\u4e47",
    "\u4e0b",
    "\u53b6",
    "\u5344",
    "\u5de5",
    "\u4e01",
    "\u957f",
    "\u4e5a",
    "\u4ece",
    "\ud842\ude28",
    "\u53e3",
    "\u5c38",
    "\u353f",
    "\u5c3a",
    "\u4e02",
    "\u4e05",
    "\u51f5",
    "\u30ea",
    "\u5c71",
    "\u4e42",
    "\u4e2b",
    "\u4e59",
]

@kigcmd(command='weebify')
@rate_limit(40, 60)
async def weebify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    message = update.effective_message
    string = ""

    if message.reply_to_message:
        string = message.reply_to_message.text.lower().replace(" ", "  ")

    if args:
        string = "  ".join(args).lower()

    if not string:
        await message.reply_text("Usage is `/weebify <text>`", parse_mode=ParseMode.MARKDOWN)
        return

    for normiecharacter in string:
        if normiecharacter in normiefont:
            weebycharacter = weebyfont[normiefont.index(normiecharacter)]
            string = string.replace(normiecharacter, weebycharacter)

    if message.reply_to_message:
        await message.reply_to_message.reply_text(string)
    else:
        await message.reply_text(string)
