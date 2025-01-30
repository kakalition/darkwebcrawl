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
    base_url = "http://suprbaydvdcaynfo4dgdzgxb4zuso7rftlil5yg5kqjefnw4wq4ulcad.onion"

    def __init__(self):
        super().__init__()
        self.mongodb_client = MongoDBClient(
            host=MONGO_HOST, port=MONGO_PORT, username=MONGO_USER, password=MONGO_PASS, database_name="allnewdarkweb"
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
            last_page = soup.find_all('a', class_='pagination_last')[-1].text
            return int(last_page.strip())
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
                        # If not first iteration, navigate to specific page URL
                        if current_page > 1:
                            page_url = f"{url}&page={current_page}"
                            self.driver.get(page_url)
                            time.sleep(5)
                            soup = self._get_body_html()

                        # Find all tr with class inline_row
                        inline_rows = soup.find_all('tr', class_='inline_row')
                        
                        for inline_row in inline_rows:
                            # Find all td in this tr
                            tds = inline_row.find_all('td')
                            
                            # Ensure there are at least 5 td
                            if len(tds) >= 6:
                                # Take the 2nd td (index 1) for main link
                                td_link = tds[2]
                                
                                # Take the 3rd td (index 2) for additional information
                                td_post = tds[3]
                                
                                td_post_text = td_post.get_text(strip=True) if td_post else ''
                                
                                # If post text is empty or '0', replace with '1'
                                if not td_post_text or td_post_text == '0':
                                    td_post_text = '1'
                                
                                # Find div in link td without any class
                                div1 = td_link.find('div', class_=None)
    
                                span = div1.find('span')
                                
                                if span:
                                    # Find <a> tag in span
                                    link = span.find('a')
                                    
                                    if link:
                                        href = link.get('href')
                                        
                                        # Ensure href starts with 'Thread'
                                        if href and href.startswith('Thread'):
                                            # Remove ?action=newpost from the URL
                                            full_link = f"suprbay,{self.base_url}/{href.split('?')[0]},0"
                                            total_links += 1
                                            csv_writer.writerow([
                                                full_link,  # First column: site_name 
                                                td_post_text,  # Second column: post
                                                # current_page  # Third column: page
                                            ])
                                            logging.info(f"Link {total_links}: {full_link}, Post: {td_post_text}, Page: {current_page}")

                    logging.info(f"Total links found: {total_links}")
                    return total_links

            except (TimeoutException, NoSuchElementException, WebDriverException) as e:
                logging.error(f"Attempt {attempt + 1} failed: {e}")
                time.sleep(10)  # Wait before retrying
            
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
            # Initialize the driver if not already done
            if not self.driver:
                self.init_driver()

            total = self.scrape(url)
            logging.info(f"Crawler completed for {url}!")
            return total
        except Exception as e:
            logging.error(f"Crawler failed: {e}")
            return 0