import asyncio
import os
import traceback
from dataclasses import dataclass
from enum import Enum, auto

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.telegram_utils import TelegramUtils
from scrapers.scrapers import get_scrapers
from utils.db_manager import DBManager
from utils.logger import setup_logger


class CommandType(Enum):
    START = auto()
    HELP = auto()
    SUBSCRIBE = auto()
    SHOW_SUBSCRIPTIONS = auto()
    ACTIVE_FREEBIES = auto()


@dataclass
class Command:
    type: CommandType
    command: str
    description: str


class TelegramBot:
    COMMANDS = [
        Command(CommandType.START, "start", "Start"),
        Command(CommandType.HELP, "help", "⚙️ Get list of commands"),
        Command(CommandType.SUBSCRIBE, "show_subscriptions", "👀 Show subscriptions"),
        Command(CommandType.ACTIVE_FREEBIES, "show_freebies", "🎁 Show available freebies"),
    ]

    def __init__(self, db_manager: DBManager):
        self.logger = setup_logger(__name__)
        self.logger.info("Initializing...")

        token = os.environ["TELEGRAM_BOT_TOKEN"]
        self.admin_user_id = os.environ["TELEGRAM_ADMIN_USER_ID"]

        self.db_manager = db_manager
        self.scrapers = {scraper.get_scraper_name(): scraper for scraper in get_scrapers()}

        self.application = Application.builder().token(token).post_init(self._post_init).build()
        self._setup_handlers()

        self.logger.info("Initialization complete")

    def start(self):
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

    async def notify_subscribers(self, scraper: str, message: str):
        subscribers = self.db_manager.get_scraper_subscribers(scraper)
        reply_markup = self._get_keyboard_markup()

        tasks = []
        for user_id in subscribers:
            task = self.application.bot.send_message(
                chat_id=user_id, text=message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for user_id, result in zip(subscribers, results, strict=True):
            if isinstance(result, Exception):
                self.logger.error(f"Failed to send message to user {user_id}: {result}")

    async def _post_init(self, application: Application) -> None:
        commands = [(cmd.command, cmd.description) for cmd in self.COMMANDS]
        await self.application.bot.set_my_commands(commands)

    def _setup_handlers(self):
        self.application.add_error_handler(self._handle_error)

        self.commands_callbacks = {}
        for command in self.COMMANDS:
            callback_method = getattr(self, f"_{command.command}_command")
            self.application.add_handler(CommandHandler(command.command, callback_method))
            self.commands_callbacks[command.command] = callback_method

        self.application.add_handler(CallbackQueryHandler(self._handle_callback))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))

    async def _handle_error(self, update: Update, context: CallbackContext):
        try:
            exception = context.error
            stack_trace = "".join(traceback.format_exception(None, exception, exception.__traceback__))
            self.logger.error(f"Exception occurred: {exception}\n\n{stack_trace}")

            exception_text = TelegramUtils.escape_markdown_v2_code(str(exception))
            stack_trace_text = TelegramUtils.escape_markdown_v2_code(stack_trace)
            error_message = (
                f"⚠️ *An exception occurred*:\n```\n{exception_text}\n```\n\nStack trace:\n```\n{stack_trace_text}\n```"
            )
            await self.application.bot.send_message(
                chat_id=self.admin_user_id, text=error_message, parse_mode=ParseMode.MARKDOWN_V2
            )
        except Exception as e:
            inner_stack_trace = "".join(traceback.format_exception(None, e, e.__traceback__))
            self.logger.error(
                f"Failed to send error message to admin: {e}\n\n{inner_stack_trace}\n\nOriginal error: {exception}"
            )

    def _get_keyboard_markup(self, exclude_commands: list[CommandType] | None = None) -> InlineKeyboardMarkup:
        keyboard = [
            [InlineKeyboardButton(cmd.description, callback_data=cmd.command)]
            for cmd in self.COMMANDS
            if cmd.type not in (exclude_commands or []) + [CommandType.START]
        ]
        return InlineKeyboardMarkup(keyboard)

    async def _help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.callback_query:
            await update.callback_query.answer("⚙️ Here are available commands...")
        await self._respond(update, "⚙️ Choose a command:")

    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.callback_query:
            await update.callback_query.answer("👋 Hello there!")
        await self._respond(update, "Welcome\\! 👋\n\n⚙️ Choose a command:")

    async def _show_subscriptions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.callback_query:
            await update.callback_query.answer("👀 Here's what you can monitor...")

        current_scrapers = self.db_manager.get_user_subscriptions(update.effective_user.id)
        keyboard = []
        for scraper_name in self.scrapers:
            name = self.scrapers[scraper_name].get_friendly_name()
            subscribed = scraper_name in current_scrapers
            if subscribed:
                keyboard.append([InlineKeyboardButton(f"❌ Remove {name}", callback_data=f"sub/rem/{scraper_name}")])
            else:
                keyboard.append([InlineKeyboardButton(f"✔️ Add {name}", callback_data=f"sub/add/{scraper_name}")])

        keyboard.append([InlineKeyboardButton("↩ Back", callback_data="help")])

        text = "👀 Update your subscriptions"
        await self._respond(update, text, reply_markup=InlineKeyboardMarkup(keyboard))

    async def _show_freebies_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.callback_query:
            await update.callback_query.answer("🎁 Here's what's free now...")

        user_id = update.effective_user.id
        subscriptions = self.db_manager.get_user_subscriptions(user_id)
        messages = ["🎁 *Available assets for your subscriptions*"]
        for scraper_name in subscriptions:
            if scraper := self.scrapers.get(scraper_name):
                assets = self.db_manager.get_assets(scraper_name)
                messages.append(scraper.create_message(assets))
        freebies_text = "\n\n".join(messages)

        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(freebies_text, parse_mode=ParseMode.MARKDOWN_V2)
            except BadRequest as e:
                self.logger.warning(f"Failed to edit message, sending a new one: {e}")
                await update.effective_message.reply_text(freebies_text, parse_mode=ParseMode.MARKDOWN_V2)
        else:
            await update.effective_message.reply_text(freebies_text, parse_mode=ParseMode.MARKDOWN_V2)
        await update.effective_message.reply_text(
            "⚙️ Choose a command:", reply_markup=self._get_keyboard_markup(), parse_mode=ParseMode.MARKDOWN_V2
        )

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = update.effective_user.id
        command_parts = query.data.split("/")

        if len(command_parts) == 1:
            command = command_parts[0]
            if handler := self.commands_callbacks.get(command):
                await handler(update, context)
            else:
                self.logger.error(f"Unknown command: {command}")
                await query.answer("⚠️ Error: Unknown command")
                await self._respond(update, "⚠️ Error: Unknown command")

        elif command_parts[0] == "sub":
            action, scraper = command_parts[1:]
            name = self.scrapers[scraper].get_friendly_name()
            if action == "add":
                self.db_manager.add_subscription(user_id, scraper)
                await query.answer(f"✔️ Subscribed to {name}")
                await self._show_subscriptions_command(update, context)
            elif action == "rem":
                self.db_manager.remove_subscription(user_id, scraper)
                await query.answer(f"❌ Unsubscribed from {name}")
                await self._show_subscriptions_command(update, context)
            else:
                self.logger.error(f"Unknown subscription action: {action}")
                await query.answer("⚠️ Invalid subscription action")

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._respond(update, "⚙️ Use commands the following commands:")

    async def _respond(self, update: Update, message: str, reply_markup: InlineKeyboardMarkup | None = None):
        reply_markup = reply_markup or self._get_keyboard_markup()

        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(
                    message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2
                )
                return
            except BadRequest as e:
                if "not modified" in str(e).lower():
                    return
                self.logger.warning(f"Failed to edit message, sending a new one: {e}")

        await update.effective_message.reply_text(message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)
