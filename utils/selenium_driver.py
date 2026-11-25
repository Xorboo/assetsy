import os
import time

from selenium import webdriver
from urllib3.exceptions import MaxRetryError

CONNECT_ATTEMPTS = 12
CONNECT_DELAY_SECONDS = 10


def get_driver():
    chrome_options = webdriver.ChromeOptions()
    # eager: storefront pages take forever to fire 'load'; scrapers wait for their own elements
    chrome_options.page_load_strategy = "eager"
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )

    selenium_url = os.environ.get("SELENIUM_URL", "http://localhost:4444/wd/hub")
    driver = _connect(selenium_url, chrome_options)
    driver.set_page_load_timeout(30)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
    return driver


def _connect(selenium_url, chrome_options):
    # the chrome container can be mid-restart when the daily scrape fires
    for attempt in range(1, CONNECT_ATTEMPTS + 1):
        try:
            return webdriver.Remote(command_executor=selenium_url, options=chrome_options)
        except MaxRetryError:
            if attempt == CONNECT_ATTEMPTS:
                raise
            time.sleep(CONNECT_DELAY_SECONDS)
