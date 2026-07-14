# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Assetsy is a Python bot that scrapes game-asset marketplaces (Unity Asset Store publisher sale, Unreal Fab Marketplace) for free assets once a day and notifies subscribed Telegram users when the freebies change. State lives in MongoDB; scraping runs through a remote Selenium Chrome instance.

## Commands

```powershell
# Run everything (mongo + selenium chrome + bot) — the normal way to run it
docker compose up --build

# Run the bot locally against dockerized mongo/chrome (needs .env, see .env.template)
python assetsy.py

# Lint/format (ruff, config in ruff.toml: line-length 119)
ruff check .
ruff format .
```

There are no tests.

`docker-compose.override.yml` supplies local dev credentials/env; production supplies env vars externally (compose files list empty `KEY:` entries that pass through from the host/.env). `mongo-init.js` runs only on first mongo startup (creates the app user and collections) — wiping the mongo volume is required to re-run it.

## Architecture

Entry point `assetsy.py` wires three singletons and starts an APScheduler job that runs all scrapers daily:

- **`utils/db_manager.py`** — `DBManager`, thin pymongo wrapper over two collections: `scraped_data` (one doc per scraper: `{scraper, assets}`) and `telegram_users` (`{user_id, subscriptions: [scraper_name]}`).
- **`bot/bot.py`** — `TelegramBot` (python-telegram-bot, polling). Commands/inline keyboards for subscribing per-scraper and listing current freebies. All outgoing text is MarkdownV2 — always escape via `bot/telegram_utils.py` (`escape_markdown_v2`, `_url`, `_code` variants) or Telegram rejects the message. Errors are forwarded to `TELEGRAM_ADMIN_USER_ID`.
- **`scrapers/`** — one class per marketplace implementing `ScraperInterface` (`get_scraper_name` = stable DB/subscription key, `get_firendly_name` [sic], `scrape_data() -> dict`, `create_message(data) -> str`). `scrapers/scrapers.py:get_scrapers()` is the single registry — new scrapers are added there and picked up by both `ScraperManager` and the bot automatically.
- **`scrapers/scraper_manager.py`** — the change-detection loop: compares fresh `scrape_data()` output against the stored dict with `!=`; only on difference does it write to DB and notify subscribers. Scrapers must therefore return deterministic dicts (stable keys/ordering) or every run looks like a change.
- **`utils/selenium_driver.py`** — `get_driver()` returns a remote headless Chrome (`SELENIUM_DOMAIN`, docker service `chrome`) with anti-bot-detection tweaks. Scrapers must `driver.quit()` in a `finally`.

## Gotchas

- `requirements.txt` is UTF-16 encoded; keep that encoding when editing or pip in the Dockerfile may choke on a mixed rewrite.
- The scraper name strings (`"unity"`, `"unreal_fab_marketplace"`) are persisted in user subscription docs — renaming one silently orphans existing subscriptions.
- `ScraperInterface.get_firendly_name` is misspelled but load-bearing; implementations and callers all use the misspelling.
