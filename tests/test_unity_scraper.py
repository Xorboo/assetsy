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
