import asyncio
import logging
from types import SimpleNamespace

import pytest
from telegram.error import NetworkError, TimedOut

from bot.bot import TelegramBot


class FakeTelegramBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, **kwargs):
        self.sent.append(kwargs)


def _run_error_handler(error):
    fake_bot = FakeTelegramBot()
    self = SimpleNamespace(logger=logging.getLogger("test"), admin_user_id=1, application=SimpleNamespace(bot=fake_bot))
    asyncio.run(TelegramBot._handle_error(self, None, SimpleNamespace(error=error)))
    return fake_bot.sent


@pytest.mark.parametrize("error", [NetworkError("httpx.ReadError: "), TimedOut()])
def test_network_errors_do_not_alert_admin(error):
    assert _run_error_handler(error) == []


def test_other_errors_alert_admin():
    assert len(_run_error_handler(ValueError("boom"))) == 1
