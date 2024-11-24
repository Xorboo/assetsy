import asyncio
import os
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from scrapers.scrapers import get_scrapers
from utils.db_manager import DBManager
from utils.logger import setup_logger


class TelegramBot:
    def __init__(self, db_manager: DBManager):
        self.logger = setup_logger(__name__)
        self.logger.info("Initializing...")
        token = os.environ["TELEGRAM_BOT_TOKEN"]
        self.db_manager = db_manager
        self.scrapers = get_scrapers()
        self.scraper_names = [scraper.get_scraper_name() for scraper in self.scrapers]
        self.application = Application.builder().token(token).build()
        self._setup_handlers()
        self.logger.info("Done")

    def _setup_handlers(self):
        self.application.add_handler(CommandHandler("start", self._start_command))
        self.application.add_handler(CommandHandler("help", self._help_command))
        self.application.add_handler(CommandHandler("subscribe", self._show_subscription_options))
        self.application.add_handler(CommandHandler("my_subscriptions", self._show_subscriptions))
        self.application.add_handler(CommandHandler("active_freebies", self._show_active_freebies))
        self.application.add_handler(CallbackQueryHandler(self._handle_subscription_callback))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))

    @staticmethod
    def commands_text():
        return (
            "Available commands:\n"
            " - /help - Get list of comands\n"
            " - /subscribe - Subscribe to scrapers\n"
            " - /my_subscriptions - View your subscriptions\n"
            " - /active_freebies - Show available freebies"
        )

    async def _respond(self, update: Update, message: str, reply_markup: InlineKeyboardMarkup = None):
        reply_markup = reply_markup or self._get_main_commands_markup()

        if update.message:
            await update.message.reply_text(message, reply_markup=reply_markup)
        elif update.callback_query:
            await update.callback_query.edit_message_text(message, reply_markup=reply_markup)
        else:
            self.logger.warning(f"Unknown update object:\n{update}")

    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._respond(
            update, f"Welcome! 👋\n\n{self.commands_text()}", reply_markup=self._get_main_commands_markup()
        )

    async def _help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._respond(
            update, self.commands_text(), reply_markup=self._get_main_commands_markup(include_help=False)
        )

    def _get_main_commands_markup(
        self, include_help: bool = True, include_show: bool = True, include_freebies: bool = True
    ) -> InlineKeyboardMarkup:
        keyboard = []
        if include_help:
            keyboard.append([InlineKeyboardButton("Get Commands", callback_data="help")])
        keyboard.append([InlineKeyboardButton("Update Subscriptions", callback_data="update")])
        if include_show:
            keyboard.append([InlineKeyboardButton("Show Subscriptions", callback_data="show")])
        if include_freebies:
            keyboard.append([InlineKeyboardButton("Get Active Freebies", callback_data="free")])
        return InlineKeyboardMarkup(keyboard)

    async def _show_subscription_options(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        current_scrapers = self.db_manager.get_user_subscriptions(user_id)
        available_scrapers = [scraper for scraper in self.scraper_names if scraper not in current_scrapers]
        self.logger.debug(f"User {user_id} current scrapers: [{current_scrapers}], available: [{available_scrapers}]")

        keyboard = []
        for scraper in available_scrapers:
            keyboard.append([InlineKeyboardButton(f"Subscribe to [{scraper}]", callback_data=f"sub/add/{scraper}")])
        for scraper in current_scrapers:
            keyboard.append(
                [InlineKeyboardButton(f"Unsubscribe from [{scraper}]", callback_data=f"sub/remove/{scraper}")]
            )
        keyboard.append([InlineKeyboardButton("Cancel", callback_data="help")])

        if not keyboard:
            await self._respond(update, "Error: No scrapers found.")
            return

        reply_markup = InlineKeyboardMarkup(keyboard)
        await self._respond(update, "Choose an option:", reply_markup=reply_markup)

    async def _show_subscriptions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        subscriptions = self.db_manager.get_user_subscriptions(user_id)

        if not subscriptions:
            await self._respond(
                update,
                "You haven't subscribed to any scrapers yet.",
                reply_markup=self._get_main_commands_markup(include_show=False),
            )
            return

        msg = "Your current subscriptions:\n" + "\n".join(f"- {sub}" for sub in subscriptions)
        await self._respond(update, msg, reply_markup=self._get_main_commands_markup(include_show=False))

    async def _show_active_freebies(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        subscriptions = self.db_manager.get_user_subscriptions(user_id)
        date_string = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"Available assets for your subscriptions on [{date_string}]:"
        for scraper_name in subscriptions:
            scraper = next((scraper for scraper in self.scrapers if scraper.get_scraper_name() == scraper_name), None)
            assets = self.db_manager.get_assets(scraper_name)
            scraper_msg = scraper.create_message(assets)
            msg += f"\n\n{scraper_msg}"
        await self._respond(update, msg, reply_markup=self._get_main_commands_markup())

    async def _handle_subscription_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = update.effective_user.id
        self.logger.info(f"Received request: {query.data}")
        commands = query.data.split("/")
        match commands[0]:
            case "help":
                await self._help_command(update, context)
            case "update":
                await self._show_subscription_options(update, context)
            case "show":
                await self._show_subscriptions(update, context)
            case "free":
                await self._show_active_freebies(update, context)
            case "sub":
                action = commands[1]
                scraper = commands[2]
                match action:
                    case "add":
                        self.db_manager.add_subscription(user_id, scraper)
                        await query.answer(f"Subscribed to {scraper}")
                        await self._respond(update, f"Successfully 'subscribed to [{scraper}]")
                    case "remove":
                        self.db_manager.remove_subscription(user_id, scraper)
                        await query.answer(f"Unsubscribed from {scraper}")
                        await self._respond(update, f"Successfully 'unsubscribed from [{scraper}]")
                    case _:
                        self.logger.error(f"Unexpected sub action [{action}]")
                        await query.answer("Unexpected response")
                        await self._respond(update, "Unexpected response")

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._respond(update, f"Use commands to interact with me.\n\n{self.commands_text()}")

    def notify_subscribers(self, scraper: str, message: str):
        subscribers = self.db_manager.get_scraper_subscribers(scraper)

        async def send_notifications():
            for user_id in subscribers:
                try:
                    await self.application.bot.send_message(chat_id=user_id, text=message)
                except Exception as e:
                    print(f"Failed to send message to user {user_id}: {e}")

        # This is wrong, needs proper cleanup or bot will raise exceptions when closing
        async def run_async():
            try:
                try:
                    asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                await send_notifications()
            finally:
                try:
                    if loop:
                        loop.close()
                except:
                    pass

        asyncio.run(run_async())

    def start(self):
        self.application.run_polling()
