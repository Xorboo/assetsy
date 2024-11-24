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

    async def process_scrapers(self):
        self.logger.info("Processing scrapers...")
        for scraper in self.scrapers:
            scraper_name = scraper.get_scraper_name()

            stored_assets = self.db_manager.get_assets(scraper_name)
            new_assets = scraper.scrape_data()

            if new_assets != stored_assets:
                self.logger.info(f"Changes detected for [{scraper_name}]")
                self.db_manager.update_assets(scraper_name, new_assets)

                message = scraper.create_message(new_assets)
                await self.bot.notify_subscribers(scraper_name, message)
            else:
                self.logger.info(f"No changes detected for [{scraper_name}]")
        self.logger.info("Scraping complete")
