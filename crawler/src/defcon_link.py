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
    base_url = "https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion"

    def __init__(self):
        super().__init__()
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
        # Find all spans with class 'pagetotal'
        last_page_spans = soup.find_all('span', class_='pagetotal')
        
        # Check if there are at least 2 spans
        if len(last_page_spans) >= 2:
            # Select the second span (index 1)
            last_page = last_page_spans[1].text
            
            # Print and return the page number
            print("ini last page>>>>>>>>", int(last_page.strip()))
            return int(last_page.strip())
        
        # Fallback if less than 2 spans are found
        elif last_page_spans:
            # Use the first span if only one exists
            last_page = last_page_spans[0].text
            print("ini last page>>>>>>>>", int(last_page.strip()))
            return int(last_page.strip())
        
        # Return 0 or raise an exception if no spans found
        else:
            logging.warning("No pagetotal spans found")
            return 0

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

    def scrape(self, url):
        """
        Main scraping method to extract links from multiple pages
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
                    for current_page in range(1, total_pages + 1):
                        if current_page > 1:
                            # Fixed pagination URL format
                            page_url = url + f'/page{current_page}'
                            print(f"Accessing page: {page_url}")  # Debug print
                            self.driver.get(page_url)
                            time.sleep(5)
                            soup = self._get_body_html()

                        # Find all tr with class inline_row
                        inline_rows = soup.find_all('tr', class_=lambda x: x and 'topic-item' in x and 'js-topic-item' in x)
                        print(f"Found {len(inline_rows)} rows on page {current_page}")  # Debug print
                        
                        for inline_row in inline_rows:
                            tds = inline_row.find_all('td')
                            
                            if len(tds) >= 5:
                                td_link = tds[1]
                                td_post = tds[3]

                                try:
                                    td_post_text = re.search(r'\d+', td_post.get_text(strip=True))
                                    td_post_text = td_post_text.group() if td_post_text else '1'
                                except:
                                    td_post_text = '1'

                                if td_post_text == '0':
                                    td_post_text = '1'
                                
                                div1 = td_link.find('div', class_='topic-wrapper')
                                
                                if div1 and div1.find('a', class_='topic-title'):
                                    links = div1.find('a', class_='topic-title')['href']
                                    full_link = f"defcon,{links},0"
                                    total_links += 1
                                    csv_writer.writerow([
                                        full_link,
                                        td_post_text,
                                    ])
                                    logging.info(f"Link {total_links}: {full_link}, Post: {td_post_text}, Page: {current_page}")

                    logging.info(f"Total links found: {total_links}")
                    return total_links

            except (TimeoutException, NoSuchElementException, WebDriverException) as e:
                logging.error(f"Attempt {attempt + 1} failed: {e}")
                time.sleep(10)
            
            except Exception as e:
                logging.error(f"Unexpected error: {traceback.format_exc()}")
                break

        logging.error("Failed to complete scraping after multiple attempts")
        return 0

    def run(self, url):
        """
        Main method to start the crawler
        """
        print("Starting crawler")
        logging.info(f"Starting crawler for {url}")
        try:
            if not self.driver:
                self.init_driver()

            total = self.scrape(url)
            logging.info(f"Crawler completed for {url}!")
            return total
        except Exception as e:
            logging.error(f"Crawler failed: {e}")
            return 0