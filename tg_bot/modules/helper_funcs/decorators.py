import logging
import time
from functools import wraps
from telegram import Update
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    InlineQueryHandler,
    ContextTypes,
    filters,
)
from tg_bot import redis_client
from typing import Optional, List, Callable, Union
from tg_bot.modules.disable import DisableAbleCommandHandler, DisableAbleMessageHandler


def rate_limit(messages_per_window: int, window_seconds: int):
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if update.effective_user is None:
                return await func(update, context)
            user_id = update.effective_user.id
            current_time = time.time()
            key = f"rate_limit:{user_id}"

            user_history = await redis_client.lrange(key, 0, -1)
            user_history = [
                float(t)
                for t in user_history
                if current_time - float(t) <= window_seconds
            ]

            if len(user_history) >= messages_per_window:
                logging.info(
                    f"Rate limit exceeded for user {user_id}. Allowed {messages_per_window} updates in {window_seconds} seconds."
                )
                return

            await redis_client.lpush(key, current_time)
            await redis_client.ltrim(key, 0, messages_per_window - 1)
            await redis_client.expire(key, window_seconds)

            return await func(update, context)

        return wrapper

    return decorator


class KigyoTelegramHandler:
    def __init__(self):
        self._handlers = []

    def _add_handler(self, handler, group: Optional[int] = None):
        self._handlers.append((handler, group))

    def register_all(self, application):
        for handler, group in self._handlers:
            if group is not None:
                application.add_handler(handler, group=group)
            else:
                application.add_handler(handler)

    def command(
        self,
        command: Union[str, List[str]],
        admin_ok: bool = False,
        can_disable: bool = True,
        group: Optional[int] = 40,
        cmd_filter=None,
    ):
        def decorator(func: Callable):
            if isinstance(command, str):
                commands = [command]
            else:
                commands = command

            kwargs = {}
            if cmd_filter is not None:
                kwargs["filters"] = cmd_filter

            if can_disable:
                handler = DisableAbleCommandHandler(
                    commands,
                    func,
                    admin_ok=admin_ok,
                    **kwargs,
                )
            else:
                handler = CommandHandler(
                    commands,
                    func,
                    **kwargs,
                )

            self._add_handler(handler, group)
            logging.debug(
                f"[KIGCMD] Loaded handler {command} for function {func.__name__}"
            )
            return func

        return decorator

    def message(
        self,
        pattern=None,
        can_disable: bool = True,
        group: Optional[int] = 60,
        friendly: Optional[str] = None,
    ):
        def decorator(func: Callable):
            message_filter = pattern if pattern else filters.ALL
            message_filter = message_filter & ~filters.UpdateType.EDITED_MESSAGE

            if can_disable:
                handler = DisableAbleMessageHandler(
                    message_filter, func, friendly=friendly
                )
            else:
                handler = MessageHandler(message_filter, func)

            self._add_handler(handler, group)
            logging.debug(f"[KIGMSG] Loaded filter for function {func.__name__}")
            return func

        return decorator

    def callbackquery(self, pattern: str = None):
        def decorator(func: Callable):
            handler = CallbackQueryHandler(func, pattern=pattern)
            self._add_handler(handler)
            logging.debug(
                f"[KIGCALLBACK] Loaded callbackquery handler for function {func.__name__}"
            )
            return func

        return decorator

    def inlinequery(
        self,
        pattern: Optional[str] = None,
        chat_types: List[str] = None,
    ):
        def decorator(func: Callable):
            handler = InlineQueryHandler(
                func,
                pattern=pattern,
                chat_types=chat_types,
            )
            self._add_handler(handler)
            logging.debug(
                f"[KIGINLINE] Loaded inlinequery handler for function {func.__name__}"
            )
            return func

        return decorator


kigyo_handler = KigyoTelegramHandler()

kigcmd = kigyo_handler.command
kigmsg = kigyo_handler.message
kigcallback = kigyo_handler.callbackquery
kiginline = kigyo_handler.inlinequery
