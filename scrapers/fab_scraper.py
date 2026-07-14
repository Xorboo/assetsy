import json
import re

from selenium.webdriver.common.by import By

from bot.telegram_utils import TelegramUtils
from scrapers.scraper_interface import ScraperInterface
from utils.logger import setup_logger
from utils.selenium_driver import get_driver

# Cloudflare 403s plain python HTTP clients (TLS fingerprinting), so this API is
# fetched through the Selenium browser instead
HOMEPAGE_LAYOUT_URL = "https://www.fab.com/i/layouts/homepage"
FREE_BLADE_TITLE = "Limited-Time Free"


class FabScraper(ScraperInterface):
    def __init__(self) -> None:
        super().__init__()
        self.logger = setup_logger(__name__)

    def get_scraper_name(self) -> str:
        return "unreal_fab_marketplace"

    def get_friendly_name(self) -> str:
        return "Unreal Engine (Fab Marketplace)"

    def scrape_data(self) -> dict:
        self.logger.info("Fetching Fab marketplace assets...")
        driver = get_driver()
        try:
            driver.get(HOMEPAGE_LAYOUT_URL)
            homepage = json.loads(driver.find_element(By.TAG_NAME, "pre").text)
        finally:
            driver.quit()
        result = self._parse_free_items(homepage)

        total_assets = len(result.get("items", []))
        self.logger.info(f"Done, found {total_assets} assets")
        return result

    def create_message(self, data: dict) -> str:
        messages = []
        end_date = TelegramUtils.escape_markdown_v2(data.get("end_date", "<Unknown end date>"))
        messages.append(f"🦭 *UE Fab Marketplace Free Assets* \\({end_date}\\):")

        for item in data.get("items", []):
            title = TelegramUtils.escape_markdown_v2(item.get("title", "<unknown>"))
            url = TelegramUtils.escape_markdown_v2_url(item.get("url", "<no-url>"))
            messages.append(f" \\- [{title}]({url})")

        if not data.get("items"):
            messages.append(" \\- ⚠️ No free items found")

        return "\n".join(messages)

    def _parse_free_items(self, homepage: dict) -> dict[str, list[dict]]:
        result = {"end_date": "", "items": []}
        self._parse_carousel_url(homepage, result)
        self._parse_blades_items(homepage, result)
        return result

    def _parse_carousel_url(self, homepage, result):
        for carousel_item in homepage.get("carousel", []):
            if carousel_item.get("title") == FREE_BLADE_TITLE:
                result["items"].append({"title": "ALL ITEMS", "url": carousel_item.get("ctaUrl")})
                break

    def _parse_blades_items(self, homepage, result):
        free_blade = None
        for blade in homepage.get("blades", []):
            title = blade.get("title", "")
            if FREE_BLADE_TITLE in title and "Until" in title:
                free_blade = blade

                date_match = re.search(r"\((.*?)\)", title) or re.search(r"Until\s+(.*)", title)
                if date_match:
                    result["end_date"] = date_match.group(1)
                break

        if not free_blade:
            return

        # everything in this blade is free — don't filter by price fields, Fab removes them
        for tile in free_blade.get("tiles", []):
            listing = tile.get("listing", {})
            uid = listing.get("uid")
            title = listing.get("title")
            if uid and title:
                result["items"].append({"title": title, "url": f"https://fab.com/listings/{uid}"})


if __name__ == "__main__":
    scraper = FabScraper()
    data = scraper.scrape_data()
    message = scraper.create_message(data)
    print(message)
