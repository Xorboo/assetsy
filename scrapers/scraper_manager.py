import asyncio

from bot.bot import TelegramBot
from scrapers.scrapers import get_scrapers
from utils.db_manager import DBManager
from utils.logger import setup_logger


class ScraperManager:
    def __init__(self, bot: TelegramBot, db_manager: DBManager):
        self.logger = setup_logger(__name__)
        self.logger.info("Initializing...")
        self.db_manager = db_manager
        self.bot = bot

        self.scrapers = get_scrapers()
        self.logger.info("Done")

    async def process_scrapers(self, force: bool = False):
        if not force and not self.db_manager.is_scraping_enabled():
            self.logger.info("Scraping is disabled, skipping")
            return

        self.logger.info("Processing scrapers...")
        self.db_manager.set_last_scrape_at()
        errors = []
        for scraper in self.scrapers:
            scraper_name = scraper.get_scraper_name()
            try:
                await self._process_scraper(scraper, scraper_name)
            except Exception as e:
                self.logger.exception(f"Scraper [{scraper_name}] failed")
                errors.append(e)
        self.logger.info("Scraping complete")

        if errors:
            raise ExceptionGroup("Some scrapers failed", errors)

    async def _process_scraper(self, scraper, scraper_name: str):
        stored_assets = self.db_manager.get_assets(scraper_name)
        new_assets = await asyncio.to_thread(scraper.scrape_data)

        if new_assets != stored_assets:
            self.logger.info(f"Changes detected for [{scraper_name}]")
            self.db_manager.update_assets(scraper_name, new_assets)

            message = scraper.create_update_message(stored_assets, new_assets)
            if message is None:
                self.logger.info(f"Change for [{scraper_name}] not notification-worthy, skipping")
                return
            await self.bot.notify_subscribers(scraper_name, message)
        else:
            self.logger.info(f"No changes detected for [{scraper_name}]")
