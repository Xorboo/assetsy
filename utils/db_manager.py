import os
import re

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
        self.logger.info("Done")

    def close(self):
        self.client.close()

    def get_assets(self, scraper_name: str) -> dict:
        result = self.scraped_data_collection.find_one({"scraper": scraper_name})
        return result["assets"] if result else {}

    def update_assets(self, scraper_name: str, assets: dict):
        self.logger.info(f"Updating data for [{scraper_name}]")
        self.scraped_data_collection.update_one({"scraper": scraper_name}, {"$set": {"assets": assets}}, upsert=True)

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
