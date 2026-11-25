import pytest

from scrapers.unity_scraper import UnityScraper


def test_create_message():
    data = {
        "assets": [
            {
                "name": "Card Game Sounds",
                "url": "https://assetstore.unity.com/packages/audio/sound-fx/card-game-sounds-112743",
                "coupon": "EPICSOUNDSANDFX2026",
            }
        ]
    }

    message = UnityScraper().create_message(data)

    assert "`EPICSOUNDSANDFX2026`" in message
    assert "[Card Game Sounds]" in message


def test_create_message_without_coupon():
    data = {"assets": [{"name": "Some-Asset", "url": "https://example.com", "coupon": None}]}

    message = UnityScraper().create_message(data)

    assert "No coupon available" in message
    assert "Some\\-Asset" in message


def test_create_message_no_assets():
    message = UnityScraper().create_message({"assets": []})

    assert "No free items found" in message


class FakeElement:
    def __init__(self, text="", href=None, children=None):
        self.text = text
        self.href = href
        self.children = children or {}

    def get_attribute(self, name):
        return self.href if name == "href" else None

    def find_element(self, by, value):
        return self.children[value][0]

    def find_elements(self, by, value):
        return self.children.get(value, [])


def test_parse_section_with_asset():
    section = FakeElement(
        children={
            "h2": [FakeElement("Card Game Sounds")],
            "a": [FakeElement(href="https://assetstore.unity.com/packages/card-game-sounds")],
            "span.body": [FakeElement("Use coupon code EPICSOUNDS at checkout")],
        }
    )

    assert UnityScraper()._parse_section(section) == {
        "name": "Card Game Sounds",
        "url": "https://assetstore.unity.com/packages/card-game-sounds",
        "coupon": "EPICSOUNDS",
    }


def test_parse_section_skips_check_back_soon_banner():
    section = FakeElement(
        children={
            "h2": [FakeElement("Check back soon!")],
            "span.body": [FakeElement("Publisher of the Week will return on December 10, 2026!")],
        }
    )

    assert UnityScraper()._parse_section(section) is None


def test_parse_section_raises_on_unknown_section_without_link():
    section = FakeElement(children={"h2": [FakeElement("Card Game Sounds")]})

    with pytest.raises(ValueError, match="Card Game Sounds"):
        UnityScraper()._parse_section(section)
