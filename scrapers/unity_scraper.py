import re

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from telegram.helpers import escape_markdown

from scrapers.scraper_interface import ScraperInterface
from utils.logger import setup_logger
from utils.selenium_driver import get_driver


class UnityScraper(ScraperInterface):
    def __init__(self) -> None:
        super().__init__()
        self.logger = setup_logger(__name__)

    def get_scraper_name(self) -> str:
        return "unity"

    def get_friendly_name(self) -> str:
        return "Unity"

    def scrape_data(self) -> dict:
        self.logger.info("Fetching Unity assets...")
        driver = get_driver()
        driver.get("https://assetstore.unity.com/publisher-sale")

        assets = []
        try:
            wait = WebDriverWait(driver, 10)
            sections = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'section[data-type="CalloutSlim"]')))
            assets = [asset for asset in map(self._parse_section, sections) if asset]
        finally:
            driver.quit()

        self.logger.info(f"Done, found {len(assets)} assets")
        return {"assets": assets}

    def create_message(self, data: dict) -> str:
        messages = []
        for asset in data.get("assets", []):
            name = escape_markdown(asset.get("name", "<unknown>"), version=2)
            url = escape_markdown(asset.get("url", "<no-url>"), version=2, entity_type="text_link")
            coupon = escape_markdown(asset.get("coupon") or "No coupon available", version=2, entity_type="code")
            messages.append(f" \\- *\\[Coupon: `{coupon}`\\]* [{name}]({url})")

        if not data.get("assets"):
            messages.append(" \\- ⚠️ No free items found")

        return "🦭 *Unity Free Assets*:\n" + "\n".join(messages)

    def _parse_section(self, section) -> dict | None:
        name = section.find_element(By.TAG_NAME, "h2").text
        links = section.find_elements(By.TAG_NAME, "a")
        if not links:
            # between sales Unity shows this banner with the same markup but no link
            if "check back soon" in name.lower():
                self.logger.info(f"Skipping placeholder section: {name}")
                return None
            raise ValueError(f"Unity sale section has no link: {name!r}")
        return {"name": name, "url": links[0].get_attribute("href"), "coupon": self._scrape_asset_coupon(section)}

    def _scrape_asset_coupon(self, section):
        text = section.find_element(By.CSS_SELECTOR, "span.body").text
        match = re.search(r"coupon code (\S+)", text, re.IGNORECASE)
        return match.group(1) if match else None


if __name__ == "__main__":
    scraper = UnityScraper()
    data = scraper.scrape_data()
    message = scraper.create_message(data)
    print(message)
