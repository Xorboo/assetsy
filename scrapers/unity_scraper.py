import re

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from bot.telegram_utils import TelegramUtils
from scrapers.scraper_interface import ScraperInterface
from utils.logger import setup_logger
from utils.selenium_driver import get_driver


class UnityScraper(ScraperInterface):
    def __init__(self) -> None:
        super().__init__()
        self.logger = setup_logger(__name__)

    def get_scraper_name(self) -> str:
        return "unity"

    def get_firendly_name(self) -> str:
        return "Unity"

    def scrape_data(self) -> dict:
        self.logger.info("Fetching Unity assets...")
        driver = get_driver()
        driver.get("https://assetstore.unity.com/publisher-sale")

        assets = []
        try:
            wait = WebDriverWait(driver, 10)
            sections = wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'section[data-type="CalloutSlim"]'))
            )
            for section in sections:
                name = self._scrape_asset_name(section)
                url = self._scrape_asset_url(section)
                coupon_code = self._scrape_asset_coupon(section)
                assets.append({"name": name, "url": url, "coupon": coupon_code})
        finally:
            driver.quit()

        self.logger.info(f"Done, found {len(assets)} assets")
        return {"assets": assets}

    def create_message(self, data: dict) -> str:
        messages = []
        for asset in data.get("assets", []):
            name = TelegramUtils.escape_markdown_v2(asset.get("name", "<unknown>"))
            url = TelegramUtils.escape_markdown_v2_url(asset.get("url", "<no-url>"))
            coupon = TelegramUtils.escape_markdown_v2(asset.get("coupon", "No coupon available"))
            messages.append(f" \\- *\\[Coupon: {coupon}\\]* [{name}]({url})")

        if not data.get("assets"):
            messages.append(" \\- ⚠️ No free items found")

        return "🦭 *Unity Free Assets*:\n" + "\n".join(messages)

    def _scrape_asset_name(self, section):
        name = "<error>"
        try:
            name = section.find_element(By.TAG_NAME, "h2").text
        except Exception as e:
            self.logger.error(f"Error extracting name: {e}")
        return name

    def _scrape_asset_url(self, section):
        url = "<error>"
        try:
            url = section.find_element(By.TAG_NAME, "a").get_attribute("href")
        except Exception as e:
            self.logger.error(f"Error extracting URL: {e}")
        return url

    def _scrape_asset_coupon(self, section):
        coupon_code = "<error>"
        try:
            coupon_code_element = section.find_element(By.CSS_SELECTOR, "span.body")
            coupon_code_text = coupon_code_element.text
            coupon_code_match = re.search(r"coupon code (\S+)", coupon_code_text, re.IGNORECASE)
            coupon_code = coupon_code_match.group(1) if coupon_code_match else None
        except Exception as e:
            self.logger.error(f"Error extracting coupon code: {e}")
        return coupon_code
