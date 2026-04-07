from functools import wraps
from telegram import error
from telegram.constants import ChatAction


async def send_message(message, text, *args, **kwargs):
    try:
        return await message.reply_text(text, *args, **kwargs)
    except error.BadRequest as err:
        if str(err) == "Reply message not found":
            return await message.reply_text(text, quote=False, *args, **kwargs)


def typing_action(func):
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.TYPING
        )
        return await func(update, context, *args, **kwargs)
    return wrapper


def send_action(action):
    def decorator(func):
        @wraps(func)
        async def wrapper(update, context, *args, **kwargs):
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id, action=action
            )
            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator
