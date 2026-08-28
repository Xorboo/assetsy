import json
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from telegram.helpers import escape_markdown

from scrapers.scraper_interface import ScraperInterface
from utils.logger import setup_logger

# Steam's search page has no plain-JSON API, but `infinite=1` makes it answer with
# {"success", "results_html", "total_count", "start"} instead of a full page.
# The query itself filters to 100%-off games, so the parser reads no price fields.
SEARCH_QUERY = "hwtype=0&maxprice=free&category1=998&specials=1&ndl=1"
SEARCH_PAGE_URL = f"https://store.steampowered.com/search/?{SEARCH_QUERY}"
SEARCH_API_URL = f"https://store.steampowered.com/search/results/?{SEARCH_QUERY}&infinite=1&cc=us&l=english&start={{start}}&count={{count}}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}
PAGE_SIZE = 100
MAX_PAGES = 20


class _ResultRowParser(HTMLParser):
    """Extracts {id, title, url} from Steam search result rows.

    Only `data-ds-appid` + `href` are required; the title falls back to the app
    slug in the URL, so a renamed title element does not break the scrape.
    """

    def __init__(self):
        super().__init__()
        self.rows = []
        self._row = None
        self._capture = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        app_id = attrs.get("data-ds-appid")
        if app_id:
            url = urllib.parse.urljoin(SEARCH_PAGE_URL, attrs.get("href", "")).split("?")[0]
            self._row = {"id": app_id, "title": "", "url": url}
            self.rows.append(self._row)
        elif self._row is not None and "title" in attrs.get("class", "").split():
            self._capture = True

    def handle_data(self, data):
        if self._capture:
            self._row["title"] += data

    def handle_endtag(self, tag):
        self._capture = False


class SteamScraper(ScraperInterface):
    def __init__(self) -> None:
        super().__init__()
        self.logger = setup_logger(__name__)

    def get_scraper_name(self) -> str:
        return "steam"

    def get_friendly_name(self) -> str:
        return "Steam Games"

    def scrape_data(self) -> dict:
        self.logger.info("Fetching Steam free games...")
        items = []
        seen = set()
        for page in range(MAX_PAGES):
            rows, total = self._fetch_page(page * PAGE_SIZE)
            if not rows:
                if total:
                    raise RuntimeError(f"Steam reports {total} results but no rows parsed, the search markup changed")
                break
            for row in rows:
                if row["id"] not in seen:
                    seen.add(row["id"])
                    items.append(self._clean_row(row))
            if len(items) >= total:
                break
        else:
            raise RuntimeError(f"Steam pagination did not terminate after {MAX_PAGES} pages")

        items.sort(key=lambda item: item["id"])
        self.logger.info(f"Done, found {len(items)} free games")
        return {"items": items}

    def create_message(self, data: dict) -> str:
        return self._format_items(f"🎮 *[Steam]({SEARCH_PAGE_URL}) 100% Off Games*:", data.get("items", []))

    def create_update_message(self, old_data: dict, new_data: dict) -> str | None:
        old_ids = {item["id"] for item in old_data.get("items", [])}
        new_items = [item for item in new_data.get("items", []) if item["id"] not in old_ids]
        if not new_items:
            return None  # giveaways only expired, nothing worth pinging about
        return self._format_items(f"🎮 *New 100% off games on [Steam]({SEARCH_PAGE_URL})*:", new_items)

    def _fetch_page(self, start: int) -> tuple[list[dict], int]:
        url = SEARCH_API_URL.format(start=start, count=PAGE_SIZE)
        request = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read())

        parser = _ResultRowParser()
        parser.feed(body.get("results_html", ""))
        return parser.rows, body.get("total_count", 0)

    def _clean_row(self, row: dict) -> dict:
        title = row["title"].strip() or self._title_from_url(row["url"])
        return {"id": row["id"], "title": title, "url": row["url"]}

    def _title_from_url(self, url: str) -> str:
        # .../app/<id>/<slug>/ - last non-empty path segment
        parts = [part for part in urllib.parse.urlparse(url).path.split("/") if part]
        return urllib.parse.unquote(parts[-1]).replace("_", " ") if parts else "<unknown>"

    def _format_items(self, header: str, items: list[dict]) -> str:
        messages = [header]
        for item in items:
            title = escape_markdown(item.get("title", "<unknown>"), version=2)
            url = escape_markdown(item.get("url", "<no-url>"), version=2, entity_type="text_link")
            messages.append(f" \\- [{title}]({url})")
        if not items:
            messages.append(" \\- ⚠️ No free games found")
        return "\n".join(messages)


if __name__ == "__main__":
    scraper = SteamScraper()
    data = scraper.scrape_data()
    message = scraper.create_message(data)
    print(message)
