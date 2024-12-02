import asyncio
import os
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from typing import List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

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
        self.db_manager = db_manager
        self.scrapers = {scraper.get_scraper_name(): scraper for scraper in get_scrapers()}

        self.application = Application.builder().token(token).post_init(self._post_init).build()
        self._setup_handlers()

        self.logger.info("Initialization complete")

    def start(self):
        self.application.run_polling()

    async def notify_subscribers(self, scraper: str, message: str):
        subscribers = self.db_manager.get_scraper_subscribers(scraper)
        reply_markup = self._get_keyboard_markup()

        tasks = []
        for user_id in subscribers:
            task = self.application.bot.send_message(chat_id=user_id, text=message, reply_markup=reply_markup)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for user_id, result in zip(subscribers, results):
            if isinstance(result, Exception):
                self.logger.error(f"Failed to send message to user {user_id}: {result}")

    async def _post_init(self, application: Application) -> None:
        commands = [(cmd.command, cmd.description) for cmd in self.COMMANDS]
        await self.application.bot.set_my_commands(commands)

    def _setup_handlers(self):
        self.commands_callbacks = {}
        for command in self.COMMANDS:
            callback_method = getattr(self, f"_{command.command}_command")
            self.application.add_handler(CommandHandler(command.command, callback_method))
            self.commands_callbacks[command.command] = callback_method

        self.application.add_handler(CallbackQueryHandler(self._handle_callback))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))

    def _get_keyboard_markup(self, exclude_commands: Optional[List[CommandType]] = None) -> InlineKeyboardMarkup:
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
        await self._respond(update, "Welcome! 👋\n\n⚙️ Choose a command:")

    async def _show_subscriptions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.callback_query:
            await update.callback_query.answer("👀 Here's what you can monitor...")

        current_scrapers = self.db_manager.get_user_subscriptions(update.effective_user.id)
        keyboard = []
        for scraper_name in self.scrapers:
            name = self.scrapers[scraper_name].get_firendly_name()
            subscribed = scraper_name in current_scrapers
            if subscribed:
                keyboard.append([InlineKeyboardButton(f"❌ Remove {name}", callback_data=f"sub/rem/{scraper_name}")])
            else:
                keyboard.append([InlineKeyboardButton(f"✔️ Add {name}", callback_data=f"sub/add/{scraper_name}")])

        keyboard.append([InlineKeyboardButton("↩ Back", callback_data="help")])

        text = "👀 Choose an option: "
        await self._respond(update, text, reply_markup=InlineKeyboardMarkup(keyboard))

    async def _show_freebies_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.callback_query:
            await update.callback_query.answer("🎁 Here's what's free now...")

        user_id = update.effective_user.id
        subscriptions = self.db_manager.get_user_subscriptions(user_id)
        messages = [f"🎁 *Available assets for your subscriptions on [{datetime.now():%Y-%m-%d %H:%M:%S}]*"]
        for scraper_name in subscriptions:
            if scraper := self.scrapers.get(scraper_name):
                assets = self.db_manager.get_assets(scraper_name)
                messages.append(scraper.create_message(assets))
        await self._respond(update, "\n\n".join(messages), reply_markup=self._get_keyboard_markup())

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
            name = self.scrapers[scraper].get_firendly_name()
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

    async def _respond(self, update: Update, message: str, reply_markup: Optional[InlineKeyboardMarkup] = None):
        reply_markup = reply_markup or self._get_keyboard_markup()

        if update.message:
            await update.message.reply_text(message, reply_markup=reply_markup)
        # Doing this to always create a new message on a query button click if possible
        elif update.effective_message:
            await update.effective_message.reply_text(
                message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2
            )
        elif update.callback_query:
            await update.callback_query.edit_message_text(
                message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2
            )
        else:
            self.logger.warning(f"Unknown update type: {update}")
