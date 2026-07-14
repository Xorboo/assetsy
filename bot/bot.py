import asyncio
import os
import traceback
from dataclasses import dataclass
from enum import Enum, auto

from telegram import BotCommandScopeChat, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden, TelegramError
from telegram.ext import (
    Application,
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)
from telegram.helpers import escape_markdown

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
        self.admin_user_id = int(os.environ["TELEGRAM_ADMIN_USER_ID"])

        self.db_manager = db_manager
        self.scraper_manager = None  # set in assetsy.py after construction (circular otherwise)
        self.scrapers = {scraper.get_scraper_name(): scraper for scraper in get_scrapers()}

        self.application = (
            Application.builder().token(token).concurrent_updates(True).post_init(self._post_init).build()
        )
        self._setup_handlers()

        self.logger.info("Initialization complete")

    def start(self):
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

    async def notify_subscribers(self, scraper: str, message: str):
        subscribers = self.db_manager.get_scraper_subscribers(scraper)
        await self._send_to_users(subscribers, message, parse_mode=ParseMode.MARKDOWN_V2)

    async def _send_to_users(self, user_ids: list[int], text: str, parse_mode: str | None = None) -> int:
        tasks = [
            self.application.bot.send_message(chat_id=user_id, text=text, parse_mode=parse_mode)
            for user_id in user_ids
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        sent = 0
        for user_id, result in zip(user_ids, results, strict=True):
            if isinstance(result, Forbidden):
                self.logger.warning(f"User {user_id} blocked the bot, removing them")
                self.db_manager.remove_user(user_id)
            elif isinstance(result, Exception):
                self.logger.error(f"Failed to send message to user {user_id}: {result}")
            else:
                sent += 1
        return sent

    async def _notify_admin(self, text: str):
        try:
            await self.application.bot.send_message(chat_id=self.admin_user_id, text=text)
        except TelegramError as e:
            self.logger.warning(f"Failed to notify admin: {e}")

    async def _post_init(self, application: Application) -> None:
        commands = [(cmd.command, cmd.description) for cmd in self.COMMANDS]
        await application.bot.set_my_commands(commands)
        try:
            await application.bot.set_my_commands(
                commands + [("admin", "🛠 Admin console")], scope=BotCommandScopeChat(chat_id=self.admin_user_id)
            )
        except TelegramError as e:
            self.logger.warning(f"Failed to set admin commands (no chat with admin yet?): {e}")

    def _setup_handlers(self):
        self.application.add_error_handler(self._handle_error)

        # keeps name/username/created_at fresh for every interacting user
        self.application.add_handler(TypeHandler(Update, self._track_user), group=-1)

        self.commands_callbacks = {}
        for command in self.COMMANDS:
            callback_method = getattr(self, f"_{command.command}_command")
            self.application.add_handler(CommandHandler(command.command, callback_method))
            self.commands_callbacks[command.command] = callback_method

        self.application.add_handler(CommandHandler("admin", self._admin_command))
        self.application.add_handler(CallbackQueryHandler(self._handle_callback))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))

    async def _track_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user and not user.is_bot:
            self.db_manager.upsert_user(user.id, user.first_name, user.username)

    async def _handle_error(self, update: Update, context: CallbackContext):
        try:
            exception = context.error
            stack_trace = "".join(traceback.format_exception(None, exception, exception.__traceback__))
            self.logger.error(f"Exception occurred: {exception}\n\n{stack_trace}")

            # keep the whole thing under Telegram's 4096-char message limit
            exception_text = escape_markdown(str(exception)[:500], version=2, entity_type="code")
            stack_trace_text = escape_markdown(stack_trace[-3000:], version=2, entity_type="code")
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
        await self._render_subscriptions(update)

    async def _render_subscriptions(self, update: Update):
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
                await self._render_subscriptions(update)
            elif action == "rem":
                self.db_manager.remove_subscription(user_id, scraper)
                await query.answer(f"❌ Unsubscribed from {name}")
                await self._render_subscriptions(update)
            else:
                self.logger.error(f"Unknown subscription action: {action}")
                await query.answer("⚠️ Invalid subscription action")
                return
            if user_id != self.admin_user_id:
                user = update.effective_user
                await self._notify_admin(f"👤 {user.first_name} (@{user.username}, {user_id}) {action} [{scraper}]")

        elif command_parts[0] == "adm":
            if user_id != self.admin_user_id:
                await query.answer("⛔ Not allowed")
                return
            await self._handle_admin_callback(update, context, command_parts[1])

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id == self.admin_user_id and context.user_data.pop("awaiting_broadcast", False):
            await self._preview_broadcast(update, context)
            return
        await self._respond(update, "⚙️ Use one of the following commands:")

    # --- Admin console ---

    async def _admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != self.admin_user_id:
            return
        await self._render_admin_menu(update)

    async def _render_admin_menu(self, update: Update):
        scraping_toggle = (
            InlineKeyboardButton("⏸ Disable daily updates", callback_data="adm/toggle")
            if self.db_manager.is_scraping_enabled()
            else InlineKeyboardButton("▶️ Enable daily updates", callback_data="adm/toggle")
        )
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📊 Stats", callback_data="adm/stats")],
                [InlineKeyboardButton("👥 Subscribers", callback_data="adm/subs")],
                [InlineKeyboardButton("🔄 Scrape now", callback_data="adm/scrape")],
                [scraping_toggle],
                [InlineKeyboardButton("📢 Broadcast", callback_data="adm/broadcast")],
                [InlineKeyboardButton("↩ Back", callback_data="help")],
            ]
        )
        await self._respond(update, "🛠 *Admin console*", reply_markup=keyboard)

    async def _handle_admin_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE, action: str):
        query = update.callback_query

        if action == "menu":
            await query.answer()
            await self._render_admin_menu(update)

        elif action == "stats":
            await query.answer()
            users = self.db_manager.get_all_users()
            lines = [
                "📊 *Stats*",
                escape_markdown(f"Users: {len(users)}", version=2),
            ]
            for scraper_name, scraper in self.scrapers.items():
                count = sum(1 for u in users if scraper_name in u.get("subscriptions", []))
                lines.append(escape_markdown(f"{scraper.get_friendly_name()}: {count} subscribers", version=2))
            enabled = self.db_manager.is_scraping_enabled()
            lines.append(escape_markdown(f"Daily updates: {'enabled ✅' if enabled else 'DISABLED ⏸'}", version=2))
            last = self.db_manager.get_last_scrape_at()
            lines.append(
                escape_markdown(f"Last scrape: {last.strftime('%Y-%m-%d %H:%M UTC') if last else 'never'}", version=2)
            )
            await self._respond(update, "\n".join(lines), reply_markup=self._admin_back_markup())

        elif action == "subs":
            await query.answer()
            lines = ["👥 *Users*"]
            for user in self.db_manager.get_all_users():
                subs = ", ".join(user.get("subscriptions", [])) or "no subscriptions"
                label = f"{user.get('first_name') or '?'} (@{user.get('username')}, {user['user_id']}): {subs}"
                lines.append(escape_markdown(f"• {label}", version=2))
            await self._respond(update, "\n".join(lines), reply_markup=self._admin_back_markup())

        elif action == "scrape":
            await query.answer("🔄 Scrape started...")

            async def run_scrape():
                await self.scraper_manager.process_scrapers(force=True)
                await self._notify_admin("✅ Manual scrape finished")

            self.application.create_task(run_scrape())
            await self._respond(update, "🔄 Scrape started\\.\\.\\.", reply_markup=self._admin_back_markup())

        elif action == "toggle":
            enabled = not self.db_manager.is_scraping_enabled()
            self.db_manager.set_scraping_enabled(enabled)
            await query.answer(f"Daily updates {'enabled ✅' if enabled else 'disabled ⏸'}")
            await self._render_admin_menu(update)

        elif action == "broadcast":
            await query.answer()
            context.user_data["awaiting_broadcast"] = True
            await self._respond(update, "📢 Send me the broadcast message:", reply_markup=self._admin_back_markup())

        elif action == "bc_send":
            draft = context.user_data.pop("broadcast_draft", None)
            if not draft:
                await query.answer("⚠️ No pending broadcast")
                return
            await query.answer("📢 Sending...")
            user_ids = [user["user_id"] for user in self.db_manager.get_all_users()]
            sent = await self._send_to_users(user_ids, draft)
            await query.edit_message_text(f"📢 Broadcast sent to {sent}/{len(user_ids)} users")

        elif action == "bc_cancel":
            context.user_data.pop("broadcast_draft", None)
            context.user_data.pop("awaiting_broadcast", None)
            await query.answer("Broadcast cancelled")
            await self._render_admin_menu(update)

        else:
            self.logger.error(f"Unknown admin action: {action}")
            await query.answer("⚠️ Unknown admin action")

    def _admin_back_markup(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[InlineKeyboardButton("↩ Admin menu", callback_data="adm/menu")]])

    async def _preview_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        draft = update.message.text
        context.user_data["broadcast_draft"] = draft
        user_count = len(self.db_manager.get_all_users())
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(f"📢 Send to {user_count} users", callback_data="adm/bc_send")],
                [InlineKeyboardButton("❌ Cancel", callback_data="adm/bc_cancel")],
            ]
        )
        # no parse_mode: the draft is shown and sent verbatim
        await update.message.reply_text(f"Preview:\n\n{draft}", reply_markup=keyboard)

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
