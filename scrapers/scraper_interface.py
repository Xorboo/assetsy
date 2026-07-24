from abc import ABC, abstractmethod


class ScraperInterface(ABC):
    @abstractmethod
    def get_scraper_name(self) -> str:
        pass

    @abstractmethod
    def get_friendly_name(self) -> str:
        pass

    @abstractmethod
    def scrape_data(self) -> dict:
        pass

    @abstractmethod
    def create_message(self, data: dict) -> str:
        pass

    def create_update_message(self, old_data: dict, new_data: dict) -> str | None:
        """Message to send subscribers when stored data changed; None skips the notification."""
        return self.create_message(new_data)
