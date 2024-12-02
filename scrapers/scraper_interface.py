from abc import ABC, abstractmethod


class ScraperInterface(ABC):
    @abstractmethod
    def get_scraper_name(self) -> str:
        pass

    @abstractmethod
    def get_firendly_name(self) -> str:
        pass

    @abstractmethod
    def scrape_data(self) -> dict:
        pass

    @abstractmethod
    def create_message(self, data: dict) -> str:
        pass
