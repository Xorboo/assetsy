# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Assetsy is a Python bot that scrapes game-asset marketplaces (Unity Asset Store publisher sale, Unreal Fab Marketplace) for limited-time free assets once a day and notifies subscribed Telegram users when the freebies change. State lives in MongoDB; scraping runs through a remote Selenium Chrome. The stack deliberately mirrors the sibling ObyWatcher project (uv, `MONGO_URI`/`MONGO_DB` env vars, auth-less local Mongo, shared Mongo in prod).

## Commands

```powershell
uv sync                      # create/refresh .venv
docker compose up --build    # full stack: mongo + selenium chrome + bot
docker compose up -d mongo chrome   # infra only, then:
python assetsy.py            # run the bot locally against dockerized mongo/chrome (.env supplies config)
python -m scrapers.fab_scraper      # run one scraper standalone (needs chrome container up)
python -m scrapers.unity_scraper
uv run ruff check .          # lint (config in pyproject.toml)
uv run ruff format .
```

There are no tests. Secrets/config come from `.env` (see `.env.template`); docker compose reads it for `TELEGRAM_*`, and `load_dotenv()` reads it for local runs. Local mongo is exposed on **27018** (27017 is ObyWatcher's).

## Architecture

Entry point `assetsy.py` wires `DBManager` → `TelegramBot` → `ScraperManager`, then registers a daily scrape job on PTB's built-in `JobQueue` (`first=1` so every restart scrapes immediately; `misfire_grace_time` covers the queue starting after Telegram init — don't schedule with plain `first=0`, the first run gets silently skipped as a misfire).

- **`utils/db_manager.py`** — thin pymongo wrapper over two collections: `scraped_data` (one doc per scraper: `{scraper, assets}`) and `telegram_users` (`{user_id, subscriptions: [scraper_name]}`).
- **`bot/bot.py`** — `TelegramBot` (python-telegram-bot v22, polling). Inline keyboards for subscribing per-scraper and listing current freebies. All outgoing text is MarkdownV2 — always escape via `bot/telegram_utils.py` (`escape_markdown_v2`, `_url`, `_code` variants) or Telegram rejects the message. Errors are forwarded to `TELEGRAM_ADMIN_USER_ID`.
- **`scrapers/`** — one class per marketplace implementing `ScraperInterface` (`get_scraper_name` = stable DB/subscription key, `get_friendly_name`, `scrape_data() -> dict`, `create_message(data) -> str`). `scrapers/scrapers.py:get_scrapers()` is the single registry — add a scraper there and both `ScraperManager` and the bot pick it up. Each scraper has a `__main__` block for standalone testing.
- **`scrapers/scraper_manager.py`** — change detection: compares fresh `scrape_data()` output against the stored dict with `!=`; only on difference does it write to DB and notify subscribers. Scrapers must return deterministic dicts or every run looks like a change.
- **`utils/selenium_driver.py`** — remote headless Chrome (`SELENIUM_URL`) with anti-bot tweaks. Uses `eager` page-load strategy: heavy storefront pages never finish their `load` event in reasonable time, so scrapers must explicitly wait for the elements they need. Scrapers must `driver.quit()` in a `finally`.
- **`utils/logger.py`** — `setup_logger()` configures the root logger once (INFO, stdout). Library logs (PTB, APScheduler) are intentionally visible; that's how silent job misfires were caught.

## Scraper fetch strategies (hard-won)

- **Fab**: `https://www.fab.com/i/layouts/homepage` returns the same JSON the homepage embeds. Cloudflare 403s plain Python HTTP clients (TLS fingerprinting — httpx fails even with browser headers/http2), so it's fetched by navigating Selenium Chrome straight to the API URL and reading the `<pre>` body. Everything in the "Limited-Time Free" blade is free — do not filter by price fields, Fab removed `discountedPrice` once already.
- **Unity**: renders `https://assetstore.unity.com/publisher-sale` and reads `section[data-type="CalloutSlim"]` elements (name, url, coupon code).

## Gotchas

- The scraper name strings (`"unity"`, `"unreal_fab_marketplace"`) are persisted in user subscription docs — renaming one silently orphans existing subscriptions.
- `data/mongo/` is a leftover bind-mount from the pre-2025 setup (compose now uses the `mongo_data` named volume); it's gitignored and safe to delete.
- The production deployment target is Coolify with a shared MongoDB (same pattern as ObyWatcher's `docker-compose.coolify.yml`) — not set up yet.
