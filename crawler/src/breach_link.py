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
    base_url = "http://breached26tezcofqla4adzyn22notfqwcac7gpbrleg4usehljwkgqd.onion"

    def __init__(self):
        super().__init__()
        self.mongodb_client = MongoDBClient(
            host=MONGO_HOST, port=MONGO_PORT, username=MONGO_USER, password=MONGO_PASS, database_name="allnewdarkweb"
        )
        self.driver = None
        self.processed_links = set()  # Set untuk tracking URL yang sudah diproses
        self.processed_nodes = set()  # 

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
        
        :param soup: BeautifulSoup object of the page
        :return: Maximum page number (int)
        """
        parent_container = soup.find("div", class_="pagination")
        total = 1  # Default to 1 if no pages are found
    
        if parent_container:
            # Find all <a> tags in the pagination container
            all_pagination = parent_container.find_all("a")

            # Iterate over all <a> tags and extract the page numbers
            page_numbers = []
            for link in all_pagination:
                # The page number is usually the text of the <a> tag (e.g., "1", "2", "3", etc.)
                page_text = link.text.strip()

                # We want to ignore links like "Previous", "Next", "Catalog", "Home", etc.
                if page_text.isdigit():
                    page_numbers.append(int(page_text))

            # Get the maximum page number from the list
            if page_numbers:
                total = max(page_numbers)
            
            return total
        else:
            return 1  # Default to 1 page if no pagination found

    def _handle_captcha(self):
        """
        More robust captcha handling with multiple strategies
        """
        try:
            # Try multiple potential captcha element locators
            captcha_locators = [
                (By.XPATH, "/html/body/div/div/div[4]"),
                (By.CLASS_NAME, "captcha-container"),
                (By.ID, "captcha"),
                (By.TAG_NAME, "iframe")
            ]

            for locator in captcha_locators:
                try:
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located(locator)
                    )
                    logging.info(f"Potential captcha detected with locator: {locator}")
                    time.sleep(10)  # Wait for manual intervention
                    return True
                except TimeoutException:
                    continue

            return False
        except Exception as e:
            logging.error(f"Captcha handling error: {e}")
            return False

    def _get_body_html(self):
        """
        Get the innerHTML of the body and parse with BeautifulSoup
        """
        bbad_body = self.driver.find_element(By.TAG_NAME, "body").get_attribute("innerHTML")
        return BeautifulSoup(bbad_body, "html.parser")

    def scrape(self, url):
        """
        Main scraping method to extract unique links from multiple pages
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # ... (kode sebelumnya tetap sama sampai loop halaman)

                # Prepare CSV file
                csv_filename = 'darkweb_links.csv'
                with open(csv_filename, 'w', newline='', encoding='utf-8') as csv_file:
                    csv_writer = csv.writer(csv_file, delimiter=',', quoting=csv.QUOTE_MINIMAL)
                    csv_writer.writerow(['site_name', 'post', 'page'])

                    total_links = 0
                    total_pages = 0

                    for current_page in range(1, total_pages + 1):
                        if current_page > 1:
                            page_url = f"{url}/page{current_page}"
                            self.driver.get(page_url)
                            time.sleep(5)
                            soup = self._get_body_html()

                        inline_rows = soup.find_all('tr', class_='inline_row')
                        
                        for inline_row in inline_rows:
                            tds = inline_row.find_all('td')
                            
                            if len(tds) >= 5:
                                td_link = tds[1]
                                td_post = tds[2]
                                
                                td_post_text = td_post.get_text(strip=True) if td_post else ''
                                if not td_post_text or td_post_text == '0':
                                    td_post_text = '1'
                                
                                div1 = td_link.find('div')
                                span = div1.find('div') if div1 else None
                                
                                if span:
                                    link = span.find('a')
                                    
                                    if link:
                                        href = link.get('href')
                                        
                                        if href:
                                            # Extract node ID dari URL
                                            node_match = re.search(r'node/(\d+)', href)
                                            if node_match:
                                                node_id = node_match.group(1)
                                                
                                                # Cek apakah node ID sudah diproses
                                                if node_id not in self.processed_nodes:
                                                    self.processed_nodes.add(node_id)
                                                    full_link = f"defcon,{self.base_url}/node/{node_id},0"
                                                    
                                                    total_links += 1
                                                    csv_writer.writerow([
                                                        full_link,
                                                        td_post_text,
                                                        current_page
                                                    ])
                                                    logging.info(f"Link {total_links}: {full_link}, Post: {td_post_text}, Page: {current_page}")
                        
                        logging.info(f"Found {total_links} unique links through page {current_page}")
                        time.sleep(2)

                    logging.info(f"Total unique links found: {total_links}")
                    return total_links

            except Exception as e:
                logging.error(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    logging.error(f"Failed after {max_retries} attempts")
                    raise
                time.sleep(10)
    
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