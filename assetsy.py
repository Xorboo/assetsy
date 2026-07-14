from datetime import timedelta

from dotenv import load_dotenv
from telegram.ext import ContextTypes

from bot.bot import TelegramBot
from scrapers.scraper_manager import ScraperManager
from utils.db_manager import DBManager
from utils.logger import setup_logger

SCRAPE_INTERVAL = timedelta(days=1)


def main():
    logger = setup_logger(__name__)
    logger.info("Starting Assetsy...")
    load_dotenv()

    db_manager = DBManager()
    bot = TelegramBot(db_manager)
    scraper = ScraperManager(bot, db_manager)

    async def scrape_job(context: ContextTypes.DEFAULT_TYPE):
        await scraper.process_scrapers()

    # misfire grace: the job queue starts after Telegram init, which would otherwise
    # silently skip the immediate first run
    bot.application.job_queue.run_repeating(
        scrape_job, interval=SCRAPE_INTERVAL, first=1, job_kwargs={"misfire_grace_time": 300}
    )

    try:
        logger.info("Starting bot...")
        bot.start()
    finally:
        db_manager.close()


if __name__ == "__main__":
    main()
