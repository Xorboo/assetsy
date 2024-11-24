import os
from typing import List

from pymongo import MongoClient

from utils.logger import setup_logger


class DBManager:
    def __init__(self):
        self.logger = setup_logger(__name__)
        self.logger.info("Initializing...")
        username = os.environ["MONGO_INITDB_ROOT_USERNAME"]
        password = os.environ["MONGO_INITDB_ROOT_PASSWORD"]
        self.client = MongoClient(f"mongodb://{username}:{password}@mongo:27017/")
        self.db = self.client["assetsy"]
        self.scraped_data_collection = self.db["scraped_data"]
        self.users_collection = self.db["subscribed_users"]
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

    def get_user_subscriptions(self, user_id: int) -> List[str]:
        user = self.users_collection.find_one({"user_id": user_id})
        return user.get("subscriptions", []) if user else []

    def get_scraper_subscribers(self, scraper_name: str) -> List[int]:
        cursor = self.users_collection.find({"subscriptions": scraper_name}, {"user_id": 1})
        return [doc["user_id"] for doc in cursor]
