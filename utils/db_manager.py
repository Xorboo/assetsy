import os
import re
from datetime import UTC, datetime

from pymongo import MongoClient

from utils.logger import setup_logger


class DBManager:
    def __init__(self):
        self.logger = setup_logger(__name__)
        self.logger.info("Initializing...")
        uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
        database = os.environ.get("MONGO_DB", "assetsy")
        self.logger.info(f"Connecting to DB '{database}' on '{re.sub(r'://[^@]+@', '://<CREDENTIALS>@', uri)}'")
        self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        self.db = self.client[database]
        self.scraped_data_collection = self.db["scraped_data"]
        self.users_collection = self.db["telegram_users"]
        self.runtime_state_collection = self.db["runtime_state"]
        self.logger.info("Done")

    def close(self):
        self.client.close()

    def get_assets(self, scraper_name: str) -> dict:
        result = self.scraped_data_collection.find_one({"scraper": scraper_name})
        return result["assets"] if result else {}

    def update_assets(self, scraper_name: str, assets: dict):
        self.logger.info(f"Updating data for [{scraper_name}]")
        self.scraped_data_collection.update_one({"scraper": scraper_name}, {"$set": {"assets": assets}}, upsert=True)

    def upsert_user(self, user_id: int, first_name: str | None, username: str | None) -> None:
        self.users_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {"first_name": first_name, "username": username, "updated_at": datetime.now(UTC)},
                "$setOnInsert": {"user_id": user_id, "subscriptions": [], "created_at": datetime.now(UTC)},
            },
            upsert=True,
        )

    def remove_user(self, user_id: int) -> None:
        self.users_collection.delete_one({"user_id": user_id})

    def get_all_users(self) -> list[dict]:
        return list(self.users_collection.find({}).sort("created_at", 1))

    def add_subscription(self, user_id: int, scraper_name: str) -> None:
        self.users_collection.update_one(
            {"user_id": user_id},
            {"$addToSet": {"subscriptions": scraper_name}, "$setOnInsert": {"user_id": user_id}},
            upsert=True,
        )

    def remove_subscription(self, user_id: int, scraper_name: str) -> None:
        self.users_collection.update_one({"user_id": user_id}, {"$pull": {"subscriptions": scraper_name}})

    def get_user_subscriptions(self, user_id: int) -> list[str]:
        user = self.users_collection.find_one({"user_id": user_id})
        return user.get("subscriptions", []) if user else []

    def get_scraper_subscribers(self, scraper_name: str) -> list[int]:
        cursor = self.users_collection.find({"subscriptions": scraper_name}, {"user_id": 1})
        return [doc["user_id"] for doc in cursor]

    def is_scraping_enabled(self) -> bool:
        doc = self.runtime_state_collection.find_one({"_id": "global"})
        return bool(doc.get("scraping_enabled", True)) if doc else True

    def set_scraping_enabled(self, enabled: bool) -> None:
        self.runtime_state_collection.update_one(
            {"_id": "global"}, {"$set": {"scraping_enabled": enabled}}, upsert=True
        )

    def set_last_scrape_at(self) -> None:
        self.runtime_state_collection.update_one(
            {"_id": "global"}, {"$set": {"last_scrape_at": datetime.now(UTC)}}, upsert=True
        )

    def get_last_scrape_at(self) -> datetime | None:
        doc = self.runtime_state_collection.find_one({"_id": "global"})
        return doc.get("last_scrape_at") if doc else None
