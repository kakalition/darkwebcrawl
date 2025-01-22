import datetime
import logging
import selenium_utils
import re
import sys
import time
from bs4 import BeautifulSoup
from pymongo import MongoClient
from bson.objectid import ObjectId

from config import (
    BINARY_PATH,
    GECKO_DRIVER_PATH,
    MONGO_HOST,
    MONGO_PASS,
    MONGO_PORT,
    MONGO_USER,
    PROFILE_PATH,
)
from src.base import BaseCrawler, DarkPost
from src.mongo import MongoDBClient
from src.selenium_config import SeleniumConfig
from utils import clean_html, fill_date
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s"
)

class DarkwebCrawler(BaseCrawler):
    base_url = "http://pitchprash4aqilfr7sbmuwve3pnkpylqwxjbj2q5o4szcfeea6d27yd.onion"

    def __init__(self):
        super().__init__()
        self.mongodb_client = MongoDBClient(
            host=MONGO_HOST, port=MONGO_PORT, username=MONGO_USER, password=MONGO_PASS
        )

    def init_driver(self):
        driver_config = SeleniumConfig(GECKO_DRIVER_PATH, BINARY_PATH, PROFILE_PATH)
        driver = driver_config.create_firefox_driver()
        driver.implicitly_wait(15)
        return driver

    # ------ Utility methods for parsing the web page ------

    def _get_body_html(self):
        bbad_body = self.driver.find_element_by_tag_name("body").get_attribute(
            "innerHTML"
        )
        return BeautifulSoup(bbad_body, "html.parser")

    def _get_thread_topic(self, soup):
        return soup.find("div", {"class": "blue bold fs-28 mt-15 mb-10"})

    def _get_thread_section(self, url):
        return url.split(self.base_url)[1].split("/")[1]

    def _get_posts(self, soup):
        # Temukan semua elemen dengan class 'mContent'
        parent_divs = soup.find_all('div', class_='mContent')
        
        # Untuk setiap elemen parent, ambil elemen anaknya (kecuali pertama dan terakhir)
        result = []
        for parent in parent_divs:
            child_divs = parent.find_all('div', recursive=False)  # Ambil hanya elemen langsung (non-recursive)
            if len(child_divs) > 2:  # Pastikan ada cukup elemen untuk skip
                skipped_divs = child_divs[1:-1]  # Skip elemen pertama dan terakhir  
                result.extend(skipped_divs)  # Tambahkan hasil yang di-skip ke result\
                    
        return result

    def _get_last_page_number(self, soup):
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
            return 1
        
    def _is_op(self, soup):
        return soup.find('a', class_='b-post__count js-show-post-link')

    # ------ Utility methods for saving the data ------

    def _save_post(self, data):
        query = {"post_id": data.post_id}

        data_dict = fill_date(data.__dict__, data.post_id, self.mongodb_client)
        # logging.error(f"data_dict: {data_dict}")

        self.mongodb_client.upsert_document('darkweb', data_dict, query)

    # ------ Main methods to scrape the content ------
        
   
    def _scrape_post(self, post):
        try:
            # Initialize list to store post IDs
            post_ids = []
            
            # Method 1: Try to get ID from the post div itself
            if post.get('id'):
                post_id = post.get('id')
                if post_id:
                    post_ids.append(post_id)
                    logging.info(f"Found post ID from div: {post_id}")
            
            # Method 2: Look for any nested elements with IDs that match post pattern
            post_elements = post.find_all(attrs={'id': re.compile(r'post-\d+|message-\d+|pid-\d+')})
            for element in post_elements:
                post_id = element.get('id')
                if post_id and post_id not in post_ids:
                    post_ids.append(post_id)
                    logging.info(f"Found post ID from nested element: {post_id}")
            
            # Method 3: Look for links containing post references
            post_links = post.find_all('a', href=re.compile(r'#p\d+|post=\d+|pid=\d+'))
            for link in post_links:
                href = link.get('href')
                # Extract numeric ID from href
                match = re.search(r'\d+', href)
                if match:
                    post_id = f"post-{match.group()}"
                    if post_id not in post_ids:
                        post_ids.append(post_id)
                        logging.info(f"Found post ID from link: {post_id}")
            
            # If no IDs found through above methods, generate a fallback ID
            if not post_ids:
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                fallback_id = f"fallback-{timestamp}-{hash(str(post))[:8]}"
                post_ids.append(fallback_id)
                logging.warning(f"No post ID found, using fallback ID: {fallback_id}")
            
            # Rest of the _scrape_post method remains the same
            poster = post.find_all('a', href=re.compile(r'@'))
            poster = poster[0].text.strip().replace('\n', '') if poster else "Unknown"
            logging.info(f"Extracted poster: {poster}")

            # Get post number and is_op first since it's needed for fallback post_id
            try:
                div_post_head = post.find('div', class_='post_head')
                if div_post_head and div_post_head.find('a'):
                    data = div_post_head.find('a').text
                    number = int(data.strip('#'))
                    is_op = (number == 1)
                else:
                    number = 0
                    is_op = False
            except (AttributeError, ValueError) as e:
                logging.error(f"Error extracting post number: {e}")
                number = 0
                is_op = False



            # Extract publication date
            try:
                timestamp_div = post.find('div', {'style': re.compile(r'color:grey'), 'title': True})
                if timestamp_div:
                    pub_str = timestamp_div.get('title')
                    logging.info(f"Found timestamp from div: {pub_str}")
                    
                    date_formats = [
                        "%Y-%m-%d %H:%M",     
                        "%Y-%m-%dT%H:%M",     
                        "%Y-%m-%d %H:%M:%S"   
                    ]
                    
                    published_at = None
                    for date_format in date_formats:
                        try:
                            published_at = datetime.datetime.strptime(pub_str, date_format)
                            logging.info(f"Successfully parsed date with format {date_format}: {published_at}")
                            break
                        except ValueError:
                            continue
                            
                    if published_at is None:
                        logging.warning(f"Could not parse timestamp: {pub_str}. Using current time.")
                        published_at = datetime.datetime.now()
                else:
                    logging.warning("No timestamp div found. Using current time.")
                    published_at = datetime.datetime.now()
                    
            except Exception as e:
                logging.error(f"Error extracting publication date: {e}")
                published_at = datetime.datetime.now()

            # Extract thread info
            try:
                thread_topic = self._get_thread_topic(self._get_body_html())
                thread_topic = thread_topic.text if thread_topic else "Unknown Topic"
                logging.info(f"Extracted thread topic: {thread_topic}")
            except Exception as e:
                logging.error(f"Error extracting thread topic: {e}")
                thread_topic = "Unknown Topic"

            try:
                thread_section = self._get_thread_section(self.driver.current_url)
                logging.info(f"Extracted thread section: {thread_section}")
            except Exception as e:
                logging.error(f"Error extracting thread section: {e}")
                thread_section = "Unknown Section"

            # Extract post content with improved error handling
            try:
                content_link = post.find('a', style=lambda value: value and 'display:block' in value)
                if content_link and content_link.text.strip():
                    post_text = content_link.text.strip()
                    logging.info(f"Found content in anchor tag: {post_text}")
                else:
                    all_links = post.find_all('a')
                    post_text = next((link.text.strip() for link in all_links if link.text.strip()), "No Content")
                
                post_media = []
                if post:
                    img_tags = post.find_all("img")
                    post_media = [x.get("src", "") for x in img_tags if x.get("src")]
                    if post_media:
                        logging.info(f"Found {len(post_media)} media items in post")

            except Exception as e:
                logging.error(f"Error extracting post content: {e}")
                post_text = "No Content"
                post_media = []

            # Create DarkPost object
            return DarkPost(
                website=self.base_url,
                thread_url=self.driver.current_url,
                thread_topic=thread_topic,
                thread_section=thread_section,
                poster=clean_html(poster),
                published_at=published_at,
                content=post_text,
                raw_content=str(post),
                post_media=post_media,
                post_id=post_id,
                is_op=is_op
            )
            
        except Exception as e:
            logging.error(f"Error while scraping post: {e}", exc_info=True)
            return None

    def scrape(self, url, idpost):
        window_opened = False

        self.driver.get(self.base_url)

        while True:
            try:
                element = WebDriverWait(self.driver, 10).until(
                    EC.visibility_of_element_located((By.XPATH, "/html/body/div/div/div[4]"))
                )

                logging.info(f"Wait captcha is ready")

                self.driver.switch_to.window(self.driver.current_window_handle)

                if not window_opened:
                    selenium_utils.bring_window_to_front(self.driver)
                    window_opened = True
            except Exception as e:
                print("No captcha")
                self.driver.get(url)
                break
            time.sleep(1)

        soup = self._get_body_html()
       
        last_page = self._get_last_page_number(soup)
        logging.info(f"total page: {last_page}")

        total = 0

        for page in range(int(last_page)):
            page_url = url + f"?p={page+1}"
            logging.info(f"Navigating to page: {page_url}")

            self.driver.get(page_url)
            time.sleep(15)

            posts = self._get_posts(self._get_body_html())
           
            logging.info(f" posts: {len(posts)}")

            for post in posts:
                data = self._scrape_post(post)
                if data:
                    logging.info(f"Saving post: {data.post_id}")
                    self._save_post(data)
                    logging.info(f"data: {data}")

                    total += 1
                    logging.info(f"Total posts: {total}")

        logging.info(f"Total posts scraped: {total}")
        return total

    def run(self, url, idpost):
        print("Post")
        logging.info(f"Starting the scraper for {url}")
        time.sleep(5)
        total = self.scrape(url, idpost)
        logging.info(f"Scraping finished for {url}!")
        return total