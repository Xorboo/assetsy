import json
import re
from html import unescape
from typing import List, Optional

from scrapers.scraper_interface import ScraperInterface
from utils.logger import setup_logger
from utils.selenium_driver import get_driver


class FabScraper(ScraperInterface):
    def __init__(self) -> None:
        super().__init__()
        self.logger = setup_logger(__name__)

    def get_scraper_name(self) -> str:
        return "unreal_fab_marketplace"

    def scrape_data(self) -> dict:
        self.logger.info("Fetching UE Marketplace assets...")
        driver = get_driver()
        driver.get("https://www.fab.com/")

        try:
            json_data = self._extract_and_parse_json(driver)
            if not json_data:
                self.logger.error("Could not find or parse JSON data")
                return
            result = self._parse_free_items(json_data)
        finally:
            driver.quit()

        total_assets = len(result.get("items", []))
        self.logger.info(f"Done, found {total_assets} assets")
        return result

    def create_message(self, data: dict) -> str:
        messages = []
        end_date = data.get("end_date", "<Unknown end date>")
        messages.append(f"🦭 *UE Fab Marketplace Free Assets* ({end_date}):")

        for item in data.get("items", []):
            title = item.get("title", "<unknown>")
            url = item.get("url", "<no-url>")
            messages.append(f" - [{title}]{url}")

        if not data.get("items"):
            messages.append(" - ⚠️ No free items found")

        return "\n".join(messages)

    def _extract_and_parse_json(self, driver) -> Optional[dict]:
        element = driver.find_element("id", "js-dom-data-prefetched-data")
        if not element:
            return None

        content = element.get_attribute("innerHTML")
        content = content.strip()
        if not content.startswith("<!--") or not content.endswith("-->"):
            return None

        content = content[4:-3]
        content = unescape(content)
        return json.loads(content)

    def _parse_free_items(self, json_data: dict) -> dict[str, List[dict]]:
        result = {"end_date": "", "items": []}
        homepage = json_data.get("/i/layouts/homepage", {})
        self._parse_carousel_url(homepage, result)
        self._parse_blades_items(homepage, result)
        return result

    def _parse_carousel_url(self, homepage, result):
        all_items_url = None
        for carousel_item in homepage.get("carousel", []):
            if carousel_item.get("title") == "Limited-Time Free":
                all_items_url = carousel_item.get("ctaUrl")
                result["items"].append({"title": "ALL ITEMS", "url": all_items_url})
                break

    def _parse_blades_items(self, homepage, result):
        blades = homepage.get("blades", [])
        free_blade = None

        for blade in blades:
            title = blade.get("title", "")
            if "Limited-Time Free" in title and "Until" in title:
                free_blade = blade

                date_match = re.search(r"\((.*?)\)", title) or re.search(r"Until\s+(.*)", title)
                if date_match:
                    result["end_date"] = date_match.group(1)
                break

        if not free_blade:
            return result

        for tile in free_blade.get("tiles", []):
            listing = tile.get("listing", {})
            price_info = listing.get("startingPrice", {})
            if price_info.get("discountedPrice") == 0:
                uid = listing.get("uid")
                title = listing.get("title")

                if uid and title:
                    result["items"].append({"title": title, "url": f"https://fab.com/listings/{uid}"})


# Old way of scraping, restricted by page width (needs additional clicks on scroll buttons)
# Easier to parse the whole data json instead
# wait = WebDriverWait(driver, 10)
# sections = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "section")))

# target_section = None
# for section in sections:
#     try:
#         title = section.find_element(By.CSS_SELECTOR, "div[class*='Typography']")
#         if "Limited-Time Free" in title.text:
#             target_section = section
#             end_date = re.search(r"Limited-Time Free \((.*?)\)", title.text)
#             if end_date:
#                 end_date = end_date.group(1)
#             break
#     except Exception:
#         continue

# if target_section:
#     asset_items = target_section.find_elements(By.CSS_SELECTOR, "ul li")

#     for item in asset_items:
#         try:
#             a_element = item.find_element(By.XPATH, ".//a[contains(@class, 'fabkit-Typography-root')]")
#             title = a_element.text.strip()
#             url = a_element.get_attribute("href")

#             assets.append({"name": title, "url": url})
#         except Exception as e:
#             self.logger.error(f"Error extracting asset details: {e}")
