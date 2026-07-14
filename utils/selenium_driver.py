import os

from selenium import webdriver


def get_driver():
    chrome_options = webdriver.ChromeOptions()
    # Don't wait for the full 'load' event of heavy storefront pages; scrapers
    # explicitly wait for the elements they need.
    chrome_options.page_load_strategy = "eager"
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )

    selenium_url = os.environ.get("SELENIUM_URL", "http://localhost:4444/wd/hub")
    driver = webdriver.Remote(command_executor=selenium_url, options=chrome_options)
    driver.set_page_load_timeout(90)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
    return driver
