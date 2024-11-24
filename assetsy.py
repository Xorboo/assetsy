from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv

from bot.bot import TelegramBot
from scrapers.scraper_manager import ScraperManager
from utils.db_manager import DBManager
from utils.logger import setup_logger


def main():
    logger = setup_logger(__name__)
    logger.info("Starting Assetsy...")
    load_dotenv()

    db_manager = DBManager()
    bot = TelegramBot(db_manager)
    scraper = ScraperManager(bot, db_manager)

    logger.info("Creating scheduler...")
    scheduler = AsyncIOScheduler()
    scheduler.add_job(scraper.process_scrapers, trigger=IntervalTrigger(minutes=1), id="scrape", replace_existing=True)

    try:
        logger.info("Starting scheduler...")
        scheduler.start()
        logger.info("Starting bot...")
        bot.start()
    except KeyboardInterrupt:
        logger.warning("Keyboard interrupt received, quitting...")
        scheduler.shutdown()
        db_manager.close()


if __name__ == "__main__":
    main()
