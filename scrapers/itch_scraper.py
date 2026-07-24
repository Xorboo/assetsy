import json
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser

from telegram.helpers import escape_markdown

from scrapers.scraper_interface import ScraperInterface
from utils.logger import setup_logger

# itch.io has no Cloudflare TLS check, plain HTTP works; ?format=json returns
# {"page", "num_items", "content": "<html cells>"} for each browse page
ON_SALE_PAGE_URL = "https://itch.io/game-assets/on-sale"
BROWSE_URL = "https://itch.io/game-assets/on-sale?page={page}&format=json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}
# ponytail: 5s tripped itch's sustained-rate limiter ~every page; 20s stays under it
PAGE_DELAY_SECONDS = 20
RATE_LIMIT_RETRIES = 4
RATE_LIMIT_RETRY_SECONDS = 60
MAX_PAGES = 150


class _GameCellParser(HTMLParser):
    """Extracts {id, title, url, sale} from itch.io browse-grid game cells."""

    def __init__(self):
        super().__init__()
        self.cells = []
        self._cell = None
        self._capture = None  # "title" | "sale" while reading text into that field

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if tag == "div" and "game_cell" in classes:
            self._cell = {"id": attrs.get("data-game_id", ""), "title": "", "url": "", "sale": ""}
            self.cells.append(self._cell)
        elif self._cell is not None and tag == "a" and "title" in classes and "game_link" in classes:
            self._cell["url"] = attrs.get("href", "")
            self._capture = "title"
        elif self._cell is not None and tag == "div" and "sale_tag" in classes:
            self._capture = "sale"

    def handle_data(self, data):
        if self._cell is not None and self._capture:
            self._cell[self._capture] += data

    def handle_endtag(self, tag):
        self._capture = None


class ItchScraper(ScraperInterface):
    def __init__(self) -> None:
        super().__init__()
        self.logger = setup_logger(__name__)

    def get_scraper_name(self) -> str:
        return "itch"

    def get_friendly_name(self) -> str:
        return "itch.io"

    def scrape_data(self) -> dict:
        self.logger.info("Fetching itch.io on-sale assets...")
        items = []
        for page in range(1, MAX_PAGES + 1):
            if page > 1:
                time.sleep(PAGE_DELAY_SECONDS)
            cells = self._fetch_page(page)
            if not cells:
                break
            items.extend(self._parse_free_items(cells))
        else:
            raise RuntimeError(f"itch.io pagination did not terminate after {MAX_PAGES} pages")

        # browse order is popularity-based and shuffles between runs; sort so
        # the manager's dict comparison only fires on real changes
        items.sort(key=lambda item: item["id"])
        self.logger.info(f"Done, found {len(items)} free assets on {page} pages")
        return {"items": items}

    def create_message(self, data: dict) -> str:
        return self._format_items(f"🦭 *[itch\\.io]({ON_SALE_PAGE_URL}) 100% Off Assets*:", data.get("items", []))

    def create_update_message(self, old_data: dict, new_data: dict) -> str | None:
        old_ids = {item["id"] for item in old_data.get("items", [])}
        new_items = [item for item in new_data.get("items", []) if item["id"] not in old_ids]
        if not new_items:
            return None  # items only expired/removed, nothing worth pinging about
        return self._format_items(f"🦭 *New 100% off assets on [itch\\.io]({ON_SALE_PAGE_URL})*:", new_items)

    def _fetch_page(self, page: int) -> list[dict]:
        request = urllib.request.Request(BROWSE_URL.format(page=page), headers=HEADERS)
        for attempt in range(RATE_LIMIT_RETRIES + 1):
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    body = json.loads(response.read())
                break
            except urllib.error.HTTPError as e:
                if e.code != 429 or attempt == RATE_LIMIT_RETRIES:
                    raise
                delay = RATE_LIMIT_RETRY_SECONDS * (attempt + 1)
                self.logger.warning(f"Rate limited on page {page}, retrying in {delay}s")
                time.sleep(delay)

        parser = _GameCellParser()
        parser.feed(body.get("content", ""))
        return parser.cells

    def _parse_free_items(self, cells: list[dict]) -> list[dict]:
        return [
            {"id": cell["id"], "title": cell["title"], "url": cell["url"]}
            for cell in cells
            if cell["sale"].strip() == "-100%"
        ]

    def _format_items(self, header: str, items: list[dict]) -> str:
        messages = [header]
        for item in items:
            title = escape_markdown(item.get("title", "<unknown>"), version=2)
            url = escape_markdown(item.get("url", "<no-url>"), version=2, entity_type="text_link")
            messages.append(f" \\- [{title}]({url})")
        if not items:
            messages.append(" \\- ⚠️ No free items found")
        return "\n".join(messages)


if __name__ == "__main__":
    scraper = ItchScraper()
    data = scraper.scrape_data()
    message = scraper.create_message(data)
    print(message)
