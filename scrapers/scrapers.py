from scrapers.fab_scraper import FabScraper
from scrapers.scraper_interface import ScraperInterface
from scrapers.steam_scraper import SteamScraper
from scrapers.unity_scraper import UnityScraper


def get_scrapers() -> list[ScraperInterface]:
    return [UnityScraper(), FabScraper(), SteamScraper()]
