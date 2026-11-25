import pytest
from urllib3.exceptions import MaxRetryError

from utils import selenium_driver


def test_connect_retries_until_chrome_is_up(monkeypatch):
    calls = []

    def fake_remote(**kwargs):
        calls.append(kwargs)
        if len(calls) < 3:
            raise MaxRetryError(None, "/wd/hub/session", "Connection refused")
        return "driver"

    monkeypatch.setattr(selenium_driver.webdriver, "Remote", fake_remote)
    monkeypatch.setattr(selenium_driver.time, "sleep", lambda _: None)
    assert selenium_driver._connect("http://chrome:4444/wd/hub", None) == "driver"
    assert len(calls) == 3


def test_connect_gives_up_after_all_attempts(monkeypatch):
    def fake_remote(**kwargs):
        raise MaxRetryError(None, "/wd/hub/session", "Connection refused")

    monkeypatch.setattr(selenium_driver.webdriver, "Remote", fake_remote)
    monkeypatch.setattr(selenium_driver.time, "sleep", lambda _: None)
    with pytest.raises(MaxRetryError):
        selenium_driver._connect("http://chrome:4444/wd/hub", None)
