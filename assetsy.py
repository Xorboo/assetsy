from apscheduler.schedulers.background import BackgroundScheduler
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
    scheduler = BackgroundScheduler()
    scheduler.add_job(scraper.process_scrapers, "interval", minutes=1)

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
