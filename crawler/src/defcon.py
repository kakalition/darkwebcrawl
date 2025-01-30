import datetime
import logging
import re
import time

from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException
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

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(message)s')

class DarkwebCrawler(BaseCrawler):
    base_url = "https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion"

    def __init__(self):
        super().__init__()
        self.mongodb_client = MongoDBClient(
            host=MONGO_HOST,
            port=MONGO_PORT,
            username=MONGO_USER,
            password=MONGO_PASS,
            database_name="allnewdarkweb"
        )

    def init_driver(self):
        driver_config = SeleniumConfig(GECKO_DRIVER_PATH, BINARY_PATH, PROFILE_PATH)
        driver = driver_config.create_firefox_driver()
        driver.implicitly_wait(15)
        return driver


    # ------ Utility methods for parsing the web page ------
    
    def _get_body_html(self):
        bbad_body = self.driver.find_element_by_tag_name("body").get_attribute("innerHTML")
        return BeautifulSoup(bbad_body, 'html.parser')

    def _get_thread_topic(self, soup):
        return soup.find('h1', class_="main-title js-main-title hide-on-editmode")

    def _get_thread_section(self, soup):
        return soup.find('ul', id=re.compile(r"breadcrumbs"))

    def _get_posts(self, soup):
        try:
            # logging.info("Attempting to find posts container...")
            parent_container = soup.find('ul', attrs={"class": "conversation-list list-container h-clearfix thread-view"})
            
            if not parent_container:
                # logging.warning("Main container not found, trying alternative class...")
                parent_container = soup.find('ul', class_="conversation-list")
            
            if parent_container:
                posts = parent_container.find_all('li', recursive=False)
                # logging.info(f"Found {len(posts)} posts")
                return posts
            else:
                # logging.error("Could not find posts container")
                return []
                
        except Exception as e:
            logging.error(f"Error in _get_posts: {e}")
            return []

    def _get_last_page_number(self, soup):
        last_page = soup.find('span', class_='pagetotal').text
        print("ini llast pagee>>>>>>>>", int(last_page.strip()))
        return int(last_page.strip())
    
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
            # Tambahkan logging untuk debug
            # logging.info("Starting to scrape post...")
            
            # Cek struktur post
            # logging.info(f"Post structure: {post}")
            
            # Cari poster dengan pengecekan bertahap
            poster_elem = post.find('span', attrs={"itemprop": "name"})
            if not poster_elem:
                # logging.warning("Poster element not found with itemprop=name, trying alternative...")
                poster_elem = post.find('span', class_="post-name")
            
            if poster_elem:
                poster = poster_elem.text
                # logging.info(f"Found poster: {poster}")
            else:
                logging.error("Could not find poster element")
                poster = "Unknown"

            # Cek class dari post untuk is_op
            try:
                is_op = 'b-post--first' in post.get('class', [])
                # logging.info(f"Is OP post: {is_op}")
            except Exception as e:
                logging.error(f"Error checking is_op: {e}")
                is_op = False

            # Cari timestamp dengan error handling
            try:
                pub_str = post.find('time', attrs={"itemprop": "dateCreated"})
                time = pub_str.get('datetime') if pub_str else None
                # logging.info(f"Found timestamp: {time}")
            except Exception as e:
                logging.error(f"Error getting timestamp: {e}")
                time = None

            # Cari konten post dengan multiple attempts
            try:
                content_elem = post.find('div', attrs={"class": "js-post__content-text restore h-wordwrap"})
                if not content_elem:
                    # logging.warning("Content element not found with primary class, trying alternatives...")
                    content_elem = post.find('div', class_="post-content")
                
                post_content = content_elem.text if content_elem else ""
                # logging.info(f"Found content length: {len(post_content)}")
            except Exception as e:
                logging.error(f"Error getting post content: {e}")
                post_content = ""

            # Get thread info with better error handling
            try:
                soup = self._get_body_html()
                thread_topic = self._get_thread_topic(soup)
                thread_section = self._get_thread_section(soup)
                
                if thread_topic and thread_section:
                    topic_text = thread_topic.text.strip()
                    section_rapi = list(filter(None, thread_section.text.split("\n")))
                    # logging.info(f"Found thread topic: {topic_text}")
                else:
                    logging.error("Could not find thread topic or section")
                    topic_text = "Unknown"
                    section_rapi = []
            except Exception as e:
                logging.error(f"Error getting thread info: {e}")
                topic_text = "Unknown"
                section_rapi = []

            # Create post object
            dark_post = DarkPost(
                website=self.base_url,
                thread_url=self.driver.current_url,
                thread_topic=topic_text,
                thread_section=section_rapi,
                poster=poster,
                published_at=time,
                content=post_content,
                raw_content=str(post),
                post_media=None,
                post_id=f"{self.driver.current_url}#{poster}_{time}",  # More unique post_id
                is_op=is_op
            )
            
            logging.info("Successfully created DarkPost object")
            return dark_post

        except Exception as e:
            logging.error(f"Critical error in _scrape_post: {str(e)}", exc_info=True)
            return None
        
    def scrape(self, url, idpost):
        try:
            self.driver.get(self.base_url)
            time.sleep(10)
            self.driver.get(url)
            time.sleep(15)

            # Coba menangani timeout pada proses pengambilan halaman
            try:
                soup = self._get_body_html()
                last_page = self._get_last_page_number(soup)
                total = 0

                for page in range(last_page):
                    page_url = url + f'/page{page + 1}'
                    logging.info(f'Navigating to page: {page_url}')

                    self.driver.get(page_url)
                    time.sleep(15)

                    posts = self._get_posts(self._get_body_html())

                    logging.info(f"posts: {len(posts)}")

                    for post in posts:
                        data = self._scrape_post(post)
                        if data:
                            logging.info(f"Saving post: {data.post_id}")
                            self._save_post(data)
                            logging.info(f"data: {data}")

                            total += 1
                            logging.info(f"Total posts: {total}")

                logging.info(f'Total posts scraped: {total}')
                return total
            except TimeoutException as e:
                logging.error(f"Timeout error occurred: {str(e)}")
                raise  # Reraise exception to go to the final block and close the browser
        except Exception as e:
            logging.error(f"Error in scraping: {str(e)}", exc_info=True)
            return 0
        finally:
            # Close Tor browser even if an error occurs
            logging.info("Closing Tor browser")
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
