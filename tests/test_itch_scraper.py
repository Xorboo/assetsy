from scrapers.itch_scraper import ItchScraper, _GameCellParser

# Trimmed-down copy of a real browse ?format=json "content" cell
CELL_TEMPLATE = """
<div data-game_id="{id}" class="game_cell has_cover lazy_images" dir="auto">
  <div class="game_cell_data">
    <div class="game_title">
      <a data-action="game_grid" class="title game_link" href="{url}">{title}</a>
      <a href="/s/1/sale" class="price_tag meta_tag sale">
        <div class="price_value">9.97€</div>
        <div class="sale_tag">{sale}</div>
      </a>
    </div>
    <div class="game_text">Some description</div>
  </div>
</div>
"""


def make_content(*cells: dict) -> str:
    return "".join(CELL_TEMPLATE.format(**cell) for cell in cells)


def test_parses_cells():
    content = make_content(
        {"id": "1", "url": "https://a.itch.io/free", "title": "Free Pack", "sale": "-100%"},
        {"id": "2", "url": "https://b.itch.io/half", "title": "Half &amp; Off", "sale": "-50%"},
    )
    parser = _GameCellParser()
    parser.feed(content)

    assert parser.cells == [
        {"id": "1", "title": "Free Pack", "url": "https://a.itch.io/free", "sale": "-100%"},
        {"id": "2", "title": "Half & Off", "url": "https://b.itch.io/half", "sale": "-50%"},
    ]


def test_keeps_only_full_discounts():
    cells = [
        {"id": "1", "title": "Free", "url": "u1", "sale": "-100%"},
        {"id": "2", "title": "Half", "url": "u2", "sale": "-50%"},
        {"id": "3", "title": "No tag", "url": "u3", "sale": ""},
    ]

    items = ItchScraper()._parse_free_items(cells)

    assert items == [{"id": "1", "title": "Free", "url": "u1"}]


def test_update_message_only_lists_new_items():
    old = {"items": [{"id": "1", "title": "Old", "url": "u1"}]}
    new = {
        "items": [
            {"id": "1", "title": "Old", "url": "u1"},
            {"id": "2", "title": "Fresh", "url": "u2"},
        ]
    }

    message = ItchScraper().create_update_message(old, new)

    assert "Fresh" in message
    assert "Old" not in message


def test_update_message_none_when_items_only_removed():
    old = {"items": [{"id": "1", "title": "Gone", "url": "u1"}]}
    new = {"items": []}

    assert ItchScraper().create_update_message(old, new) is None


def test_create_message_escapes_markdown():
    data = {"items": [{"id": "1", "title": "Pack (Cool!)", "url": "https://a.itch.io/pack_(x)"}]}

    message = ItchScraper().create_message(data)

    assert "Pack \\(Cool\\!\\)" in message
    # inside a MarkdownV2 link URL only ')' and '\' need escaping
    assert "https://a.itch.io/pack_(x\\)" in message


def test_scrape_walks_pages_until_empty_and_sorts(monkeypatch):
    pages = {
        1: [{"id": "9", "title": "B", "url": "u9", "sale": "-100%"}],
        2: [
            {"id": "3", "title": "A", "url": "u3", "sale": "-100%"},
            {"id": "5", "title": "C", "url": "u5", "sale": "-50%"},
        ],
        3: [],
    }
    scraper = ItchScraper()
    monkeypatch.setattr(scraper, "_fetch_page", lambda page: pages[page])
    monkeypatch.setattr("scrapers.itch_scraper.time.sleep", lambda s: None)

    data = scraper.scrape_data()

    assert data == {
        "items": [
            {"id": "3", "title": "A", "url": "u3"},
            {"id": "9", "title": "B", "url": "u9"},
        ]
    }


def test_create_message_no_items():
    message = ItchScraper().create_message({"items": []})

    assert "No free items found" in message
