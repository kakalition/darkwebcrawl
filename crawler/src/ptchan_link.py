import logging
import re
import time
import traceback
import csv

from bs4 import BeautifulSoup
from config import (
    BINARY_PATH,
    GECKO_DRIVER_PATH,
    MONGO_HOST,
    MONGO_PASS,
    MONGO_PORT,
    MONGO_USER,
    PROFILE_PATH,
)
from src.base import BaseCrawler, DarkProfile
from src.mongo import MongoDBClient
from src.selenium_config import SeleniumConfig
from utils import fill_date_profile
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s"
)

class DarkwebCrawler(BaseCrawler):
    base_url = "http://jieq75a6uwqbj5sjzaxlnd7xwgs35audjmkk4g3gfjwosfrz7cp47xid.onion"

    def _init_(self):
        super()._init_()
        self.mongodb_client = MongoDBClient(
            host=MONGO_HOST, port=MONGO_PORT, username=MONGO_USER, password=MONGO_PASS
        )
        self.driver = None

    def init_driver(self):
        """
        Initialize Selenium WebDriver with specific configuration
        """
        driver_config = SeleniumConfig(GECKO_DRIVER_PATH, BINARY_PATH, PROFILE_PATH)
        self.driver = driver_config.create_firefox_driver()
        self.driver.implicitly_wait(15)
        return self.driver

    def _get_last_page_number(self, soup):
        """
        Extract the last page number from pagination
        """
        try:
            last_page = soup.find('a', href='10.html').text
            # Remove brackets and convert to integer
            last_page = last_page.strip('[]')  # Remove square brackets
            return int(last_page)
        except Exception as e:
            logging.error(f"Error getting last page number: {e}")
            return 1  # Default to 1 page if extraction fails

    def _handle_captcha(self):
        """
        Bypass captcha handling
        """
        return False

    def _get_body_html(self):
        """
        Get the innerHTML of the body and parse with BeautifulSoup
        """
        bbad_body = self.driver.find_element(By.TAG_NAME, "body").get_attribute("innerHTML")
        return BeautifulSoup(bbad_body, "html.parser")

    def _format_page_url(self, base_url, page):
        # Remove any trailing slash from base url
        base_url = base_url.rstrip('/')
        
        # For first page, use index.html
        if page == 1:
            return f"{base_url}"
        
        # For subsequent pages, use number.html
        # Remove /index.html if it exists in the base_url
        base_url = base_url.replace('/index.html', '')
        return f"{base_url}/{page}.html"
    
    def scrape(self, url):
        """
        Main scraping method to extract links and count posts from nested pages
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Navigate to base URL first to handle any site-wide checks
                self.driver.get(self.base_url)
                time.sleep(5)

                # Check and handle potential captcha (now bypassed)
                if self._handle_captcha():
                    logging.warning("Captcha detection triggered")

                # Navigate to specific URL
                self.driver.get(url)
                time.sleep(10)

                # Get initial soup to check pagination
                soup = self._get_body_html()
                total_pages = self._get_last_page_number(soup)
                logging.info(f"Total pages found: {total_pages}")

                # Prepare CSV file
                csv_filename = 'darkweb_links.csv'
                with open(csv_filename, 'w', newline='', encoding='utf-8') as csv_file:
                    csv_writer = csv.writer(csv_file, delimiter=',', quoting=csv.QUOTE_MINIMAL)
                    csv_writer.writerow(['site_name', 'post'])  # Header

                    total_links = 0

                    # Loop through all pages
                    for page in range(1, total_pages + 1):
                        # If not first iteration, navigate to specific page URL
                        if page > 1:
                            page_url = self._format_page_url(url, page)
                            self.driver.get(page_url)
                            time.sleep(5)
                            soup = self._get_body_html()

                        # Find all div elements with class 'opHead title'
                        divs = soup.find_all('div', class_='post-container op')

                        # Loop through each div
                        for div in divs:
                            link = div.find('a', class_='noselect no-decoration')
                            if link:
                                href = link.get('href')
                                if href:
                                    full_link = f"{self.base_url}{href.split('?')[0].split('#')[0]}"
                                    
                                    # Visit the full link and count posts
                                    post_count = self._get_post_count(full_link)
                                    if post_count is not None:
                                        total_links += 1
                                        csv_writer.writerow(['ptchan', full_link,'0',post_count])
                                        logging.info(f"Link {total_links}: foxdick,{full_link},0,{post_count}, page: {page}")

                    logging.info(f"Total links processed: {total_links}")
                    return total_links
                
                

            except (TimeoutException, NoSuchElementException, WebDriverException) as e:
                logging.error(f"Attempt {attempt + 1} failed: {e}")
                time.sleep(10)  # Wait before retrying

            except Exception as e:
                logging.error(f"Unexpected error: {traceback.format_exc()}")
                break

        logging.error("Failed to complete scraping after multiple attempts")
        return 0

    def _get_post_count(self, link):
        """
        Visit a link and count the number of posts on the page
        """
        try:
            self.driver.get(link)
            time.sleep(5)
            soup = self._get_body_html()

            # Assuming posts are inside elements with class 'innerPost'
            posts = soup.find_all('div', class_='post-container')
            return len(posts)
        except Exception as e:
            logging.error(f"Error fetching posts from {link}: {e}")
            return None

    def run(self, url):
        """
        Main method to start the crawler
        """
        print("Starting crawler")
        logging.info(f"Starting crawler for {url}")
        try:
            # Initialize the driver if not already done
            if not self.driver:
                self.init_driver()

            total = self.scrape(url)
            logging.info(f"Crawler completed for {url}!")
            return total
        except Exception as e:
            logging.error(f"Crawler failed: {e}")
            return 0