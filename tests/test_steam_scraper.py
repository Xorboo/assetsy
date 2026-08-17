from scrapers.steam_scraper import SteamScraper, _ResultRowParser

# Trimmed-down copy of a real search/results/?infinite=1 "results_html" row
ROW_TEMPLATE = """
<a href="https://store.steampowered.com/app/{id}/{slug}/?snr=1_7_7_2300_150_1"
   data-ds-appid="{id}" data-ds-itemkey="App_{id}" class="search_result_row ds_collapse_flag">
  <div class="search_capsule"><img src="capsule.jpg"></div>
  <div class="responsive_search_name_combined">
    <div class="search_name ellipsis"><span class="{title_class}">{title}</span></div>
    <div class="search_released responsive_secondrow">Aug 6, 2012</div>
    <div class="discount_block" data-discount="100"><div class="discount_pct">-100%</div></div>
  </div>
</a>
"""


def make_html(*rows: dict) -> str:
    return "".join(ROW_TEMPLATE.format(title_class="title", **row) for row in rows)


def test_parses_rows():
    parser = _ResultRowParser()
    parser.feed(make_html({"id": "42", "slug": "Deponia", "title": "Deponia &amp; Co"}))

    assert parser.rows == [
        {
            "id": "42",
            "title": "Deponia & Co",
            "url": "https://store.steampowered.com/app/42/Deponia/",
        }
    ]


def test_title_falls_back_to_url_slug_when_element_renamed():
    html = ROW_TEMPLATE.format(id="7", slug="Some_Game", title="Some Game", title_class="app_name")
    parser = _ResultRowParser()
    parser.feed(html)

    assert SteamScraper()._clean_row(parser.rows[0])["title"] == "Some Game"


def test_scrape_paginates_dedupes_and_sorts(monkeypatch):
    pages = {
        0: ([{"id": "9", "title": "B", "url": "u9"}, {"id": "3", "title": "A", "url": "u3"}], 3),
        100: ([{"id": "3", "title": "A", "url": "u3"}, {"id": "5", "title": "C", "url": "u5"}], 3),
    }
    scraper = SteamScraper()
    monkeypatch.setattr(scraper, "_fetch_page", lambda start: pages[start])

    assert scraper.scrape_data() == {
        "items": [
            {"id": "3", "title": "A", "url": "u3"},
            {"id": "5", "title": "C", "url": "u5"},
            {"id": "9", "title": "B", "url": "u9"},
        ]
    }


def test_update_message_only_lists_new_items():
    old = {"items": [{"id": "1", "title": "Old", "url": "u1"}]}
    new = {"items": [{"id": "1", "title": "Old", "url": "u1"}, {"id": "2", "title": "Fresh", "url": "u2"}]}

    message = SteamScraper().create_update_message(old, new)

    assert "Fresh" in message
    assert "Old" not in message


def test_update_message_none_when_items_only_removed():
    old = {"items": [{"id": "1", "title": "Gone", "url": "u1"}]}

    assert SteamScraper().create_update_message(old, {"items": []}) is None


def test_create_message_escapes_markdown():
    data = {"items": [{"id": "1", "title": "Game (Cool!)", "url": "https://s.com/app/1/Game_(x)"}]}

    message = SteamScraper().create_message(data)

    assert "Game \\(Cool\\!\\)" in message
    assert "https://s.com/app/1/Game_(x\\)" in message


def test_create_message_no_items():
    assert "No free games found" in SteamScraper().create_message({"items": []})
