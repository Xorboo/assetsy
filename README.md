# Assetsy

A Telegram bot that watches game-asset marketplaces for limited-time free assets and messages you when the freebies change.

Currently watched:

- **Unity Asset Store** — [publisher sale](https://assetstore.unity.com/publisher-sale) free asset (with its coupon code)
- **Fab (Unreal)** — [limited-time free](https://www.fab.com/limited-time-free) assets

The bot checks once a day, stores the last seen state in MongoDB, and only notifies subscribers when something actually changed. Users pick which marketplaces they care about via inline keyboards (`/show_subscriptions`), and can list the current freebies any time (`/show_freebies`).

## Stack

- Python 3.12, [python-telegram-bot](https://python-telegram-bot.org/) (polling), MongoDB (pymongo)
- Selenium + headless Chrome for scraping (Fab blocks plain HTTP clients via TLS fingerprinting)
- [uv](https://docs.astral.sh/uv/) for dependencies, Docker Compose to run everything

## Running

1. Create a bot with [@BotFather](https://t.me/BotFather) and grab the token.
2. Copy the config template and fill it in:

   ```sh
   cp .env.template .env
   ```

3. Start the stack (bot + MongoDB + Selenium Chrome):

   ```sh
   docker compose up -d --build
   ```

The first scrape runs immediately on startup, then daily. Errors are forwarded to the Telegram user set in `TELEGRAM_ADMIN_USER_ID`.

### Running the bot outside docker

Useful during development — keep the infrastructure in docker but run the bot from source:

```sh
docker compose up -d mongo chrome
uv sync
uv run python assetsy.py
```

The `.env` defaults point at the ports the compose file exposes (MongoDB on `localhost:27018`, Chrome on `localhost:4444`).

Each scraper can also be run standalone, printing the message it would send:

```sh
uv run python -m scrapers.fab_scraper
uv run python -m scrapers.unity_scraper
```

## Adding a marketplace

Implement `ScraperInterface` (see `scrapers/fab_scraper.py` for the pattern) and register it in `scrapers/scrapers.py`. The scraper name is the persistent subscription key — don't rename it once live. `scrape_data()` must return the same dict for unchanged data, since change detection is a plain `!=` against the stored state.

## Development

```sh
uv run pytest
uv run ruff check .
uv run ruff format .
```

## License

See [LICENSE](LICENSE). This program is not a program of honor.
