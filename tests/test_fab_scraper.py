from scrapers.fab_scraper import FabScraper

# Trimmed-down copy of the real /i/layouts/homepage response shape
HOMEPAGE = {
    "carousel": [
        {"title": "Limited-Time Free", "ctaUrl": "https://www.fab.com/limited-time-free"},
        {"title": "On Sale", "ctaUrl": "https://www.fab.com/search?min_discount_percentage=1"},
    ],
    "blades": [
        {"title": "Recent Releases", "tiles": [{"listing": {"uid": "aaa", "title": "Not free"}}]},
        {
            "title": "Limited-Time Free (Until July 14 at 9:59 AM ET)",
            "tiles": [
                {"listing": {"uid": "uid-1", "title": "Stylized Village", "startingPrice": {"price": 39.99}}},
                {"listing": {"uid": "uid-2", "title": "Pack of tree ents", "startingPrice": {"price": 99.99}}},
                {"listing": {"title": "Broken tile without uid"}},
            ],
        },
        {"title": "Free Content", "tiles": [{"listing": {"uid": "bbb", "title": "Always free"}}]},
    ],
}


def test_parses_free_blade():
    result = FabScraper()._parse_free_items(HOMEPAGE)

    assert result["end_date"] == "Until July 14 at 9:59 AM ET"
    assert result["items"] == [
        {"title": "ALL ITEMS", "url": "https://www.fab.com/limited-time-free"},
        {"title": "Stylized Village", "url": "https://fab.com/listings/uid-1"},
        {"title": "Pack of tree ents", "url": "https://fab.com/listings/uid-2"},
    ]


def test_empty_homepage():
    result = FabScraper()._parse_free_items({})

    assert result == {"end_date": "", "items": []}


def test_create_message_escapes_markdown():
    data = {
        "end_date": "Until July 14 at 9:59 AM ET",
        "items": [{"title": "Village (Stylized!)", "url": "https://fab.com/listings/uid-1_(x)"}],
    }

    message = FabScraper().create_message(data)

    assert "Village \\(Stylized\\!\\)" in message
    # inside a MarkdownV2 link URL only ')' and '\' need escaping
    assert "https://fab.com/listings/uid-1_(x\\)" in message


def test_create_message_no_items():
    message = FabScraper().create_message({"end_date": "", "items": []})

    assert "No free items found" in message
