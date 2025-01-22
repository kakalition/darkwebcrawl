import datetime
import utils
import logging
import re
import sys
import selenium_utils
import time
from pymongo import MongoClient
from bson.objectid import ObjectId

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
    base_url = "http://breached26tezcofqla4adzyn22notfqwcac7gpbrleg4usehljwkgqd.onion"

    def __init__(self):
        super().__init__()
        self.mongodb_client = MongoDBClient(
            host=MONGO_HOST, port=MONGO_PORT, username=MONGO_USER, password=MONGO_PASS
        )
        self.processed_posts = set() 

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
        return soup.find("span", {"class": "thread-info__name rounded"})

    def _get_thread_section(self, soup):
        return soup.find("ul", {"class": re.compile(r"breadcrumb__main")})

    def _get_posts(self, soup):
        # More specific post selection to ensure we get all posts
        posts = soup.find_all('div', class_='post', recursive=True)
        logging.info(f"Found {len(posts)} posts on page")
        return posts
        
    def _get_last_page_number(self, soup):
        parent_container = soup.find(
            "div", class_="pagination"
        )
        total = 1  # Default to 1 page
        
        if parent_container:  # Only try pagination methods if container exists
            try:
                # First, try to get total pages from pagination text
                get_total = parent_container.find('span', class_="pages").text
                match = re.search(r'\((\d+)\)', get_total)
                if match:
                    total = int(match.group(1))
            except Exception as e:
                try:
                    # Try to find last page number in pagination links
                    last_page = parent_container.find("a", class_="pagination_last").text
                    if last_page:
                        total = int(last_page)
                except Exception as e:
                    # If both methods fail, default to 1 page
                    total = 1
        
        return total
      

    # ------ Utility methods for saving the data ------
    def _is_op(self, soup):
        return soup.find('a', class_='b-post__count js-show-post-link')

    def _save_post(self, data):
        query = {"post_id": data.post_id}

        data_dict = fill_date(data.__dict__, data.post_id, self.mongodb_client)
        # logging.error(f"data_dict: {data_dict}")

        self.mongodb_client.upsert_document('darkweb', data_dict, query)

    # ------ Main methods to scrape the content ------

    def _scrape_post(self, post):
        try:
            # Extract poster information
            poster_div = post.find("div", {"class": "post__user-profile largetext"})
            poster = poster_div.text.strip() if poster_div else "Unknown"
            
            div_post_head = post.find('div', class_='post_head')
            data = div_post_head.find('a').text
            
            # Extract post_id directly from the post body div, matching Suprbay's implementation
            post_body_div = post.find('div', class_='post_body scaleimages')
            post_id = post_body_div.get('id', '')
            if not post_id:
                # Fallback if no ID found - use same logic as Suprbay
                number = int(data.strip('#'))
                post_id = f"{self.driver.current_url}_{number}"
            
            # Determine if post is OP using same logic as Suprbay
            number = int(data.strip('#').replace(',', ''))
        
            is_op=(number==1)
            
            # Extract publication date
            pub_str = post.find('span', class_='post_date')
            time_str = pub_str.text if pub_str else None
            
            try:
                published_at = datetime.datetime.strptime(
                    time_str, '%b %d, %Y, %I:%M %p'
                ) if time_str else datetime.datetime.now()
            except:
                published_at = datetime.datetime.now()

            # Extract content and media
            # Get the BeautifulSoup element first, then extract text and images
            post_content = post_body_div.text if post_body_div else ""
            post_media = [x["src"] for x in post_body_div.find_all("img")] if post_body_div else []
            
            thread_topic = self._get_thread_topic(self._get_body_html())
            thread_section = self._get_thread_section(self._get_body_html())

            return DarkPost(
                website=self.base_url,
                thread_url=self.driver.current_url,
                thread_topic=thread_topic.text if thread_topic else "",
                thread_section=list(filter(None, thread_section.text.split("\n"))) if thread_section else [],
                poster=poster,
                published_at=time_str if time_str else str(published_at),
                content=clean_html(post_content),
                raw_content=str(post),
                post_media=post_media,
                post_id=post_id,
                is_op=is_op,
            )

        except Exception as e:
            logging.error(f"Error while scraping post: {e}")
            return None

    def scrape(self, url, idpost):
        self.driver.get(self.base_url)

        window_opened = False
        
        try:
            while True:
                try:
                    element = WebDriverWait(self.driver, 10).until(
                        EC.visibility_of_element_located((By.XPATH, "/html/body/div/div[2]/form/div[1]"))
                    )

                    logging.info(f"Wait captcha is ready")

                    if not window_opened:
                        selenium_utils.bring_window_to_front(self.driver)
                        window_opened = True

                except Exception as e:
                    print("No captcha")
                    self.driver.get(url)
                    break
                time.sleep(1)
                
            self.driver.minimize_window()
            soup = self._get_body_html()
            last_page = self._get_last_page_number(soup)
            logging.info(f"Total pages: {last_page}")

            total = 0
            retry_count = 3

            for page in range(int(last_page)):
                page_url = url + f"?page={page+1}"
                
                for attempt in range(retry_count):
                    try:
                        logging.info(f"Navigating to page {page+1}, attempt {attempt+1}")
                        self.driver.get(page_url)
                        time.sleep(15)
                        
                        soup = self._get_body_html()
                        posts = self._get_posts(soup)
                        
                        if not posts:
                            logging.warning(f"No posts found on page {page+1}, attempt {attempt+1}")
                            continue
                            
                        logging.info(f"Found {len(posts)} posts on page {page+1}")
                        
                        for post in posts:
                            data = self._scrape_post(post)
                            if data:
                                logging.info(f"Saving post: {data.post_id}")
                                self._save_post(data)
                                logging.info(f"data: {data}")

                                total += 1
                                logging.info(f"Total posts: {total}")
                        
                        break  # If successful, break retry loop
                        
                    except Exception as e:
                        logging.error(f"Error on page {page+1}, attempt {attempt+1}: {e}")
                        if attempt == retry_count - 1:
                            logging.error(f"Failed to scrape page {page+1} after {retry_count} attempts")

            logging.info(f"Total posts scraped: {total}")
            return total

        finally:
            # Cleanup: close the driver
            logging.info("Closing browser")
            if self.driver:
                self.driver.quit()
                self.driver = None
                
    def run(self, url, idpost):
        print("Post")
        logging.info(f"Starting the scraper for {url}")
        time.sleep(5)
        total = self.scrape(url, idpost)
        logging.info(f"Scraping finished for {url}!")
        return total