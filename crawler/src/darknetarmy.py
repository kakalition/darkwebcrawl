import datetime
import logging
import re
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


logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s"
)

class DarkwebCrawler(BaseCrawler):
    base_url = "http://dna777qa6clkmklj2yx5qamr3ge3c2wljuoyju6eav6qs45svpjlxzyd.onion"

    def __init__(self):
        super().__init__()
        self.mongodb_client = MongoDBClient(
            host=MONGO_HOST, port=MONGO_PORT, username=MONGO_USER, password=MONGO_PASS, database_name="allnewdarkweb"
        )

    def init_driver(self):
        driver_config = SeleniumConfig(GECKO_DRIVER_PATH, BINARY_PATH, PROFILE_PATH)
        driver = driver_config.create_firefox_driver()
        driver.implicitly_wait(15)
        return driver

    # ------ Utility methods for parsing the web page ------

    def _get_body_html(self):
        leftychan_body = self.driver.find_element_by_tag_name("body").get_attribute(
            "innerHTML"
        )
        return BeautifulSoup(leftychan_body, "html.parser")

    def _get_thread_topic(self, soup):
    
        thread_topic = soup.find("p", {"id": "labelName"})
        return thread_topic

    def _get_thread_section(self, url):
        thread_section = url.split(self.base_url)[1].split("/")[1]
        return thread_section

    def _get_posts(self, soup):
        """Get all posts from the page"""
        try:
            # Find all post containers
            posts = []
            # Find both original posts and replies
            op_posts = soup.find_all("div", class_="innerOP")
            reply_posts = soup.find_all("div", class_="innerPost")
            
            # Combine both types of posts
            posts.extend(op_posts)
            posts.extend(reply_posts)
            
            logging.info(f"Found {len(posts)} posts")
            return posts
        except Exception as e:
            logging.error(f"Error getting posts: {str(e)}")
            return []

    # ------ Utility methods for saving the data ------
    def _get_last_page_number(self, soup):
        parent_container = soup.find("span", id="divPages")
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
    

    def _save_post(self, data):
        query = {"post_id": data.post_id}

        data_dict = fill_date(data.__dict__, data.post_id, self.mongodb_client)
        # logging.error(f"data_dict: {data_dict}")

        self.mongodb_client.upsert_document('darkweb', data_dict, query)

    # ------ Main methods to scrape the content ------

    def _scrape_post(self, post, i):
        try:
            # Get thread info first with error handling
            soup = self._get_body_html()
            thread_topic = self._get_thread_topic(soup)
            if not thread_topic:
                logging.warning("Could not find thread topic, using default")
                thread_topic_text = "Unknown Topic"
            else:
                thread_topic_text = thread_topic.text

            thread_section = self._get_thread_section(self.driver.current_url)

            # Find post elements with null checks
            poster = post.find("a", {"class": re.compile(r"linkName  noEmailName")})
            poster_text = poster.text if poster else "Anonymous"

            published_at = None  # Set default value
            timestamp_text = post.find('span', class_="labelCreated")  # Gunakan post.find bukan soup.find
            if timestamp_text:
                # Ambil text dari elemen
                timestamp_str = timestamp_text.text.strip()
                try:
                    # Format disesuaikan dengan "MM/DD/YYYY (Day) HH:MM:SS"
                    parsed_date = datetime.datetime.strptime(timestamp_str, "%m/%d/%Y (%a) %H:%M:%S")
                    published_at = parsed_date
                except ValueError as e:
                    logging.error(f"Error parsing datetime: {e}")
                    published_at = None  # Berikan nilai default jika parsing gagal
                print("ini publish date", published_at)
                
            media = post.find('a', href=True, class_='imgLink')
            
            time_tag = post.find('time')
            content_div = post.find('div', {"class": "divMessage"})
            content_text = clean_html(content_div.text) if content_div else ""
            
            # Updated post ID generation using post_op or post_reply
            post_op = post.find('div', class_='innerOP')
            post_reply = post.find('div', class_='innerPost')
            
            if post_op:
                post_id = post_op.get('id', '')
            elif post_reply:
                post_id = post_reply.get('id', '')
            else:
                # Fallback if neither class is found
                post_id = f"{self.driver.current_url}_{i}"
                logging.warning(f"Could not find post_op or post_reply div, using fallback ID: {post_id}")

            div_post_head = post.find('div', class_='post_head')

            # Get post number from the header
            if div_post_head and div_post_head.find('a'):
                data = div_post_head.find('a').text
                number = int(data.strip('#'))  # Remove '#' character and convert to integer
                is_op = number == 1
            else:
                is_op = i == 0  # Fallback to using index if post number not found

            return DarkPost(
                website=self.base_url,
                thread_url=self.driver.current_url,
                thread_topic=thread_topic_text,
                thread_section=thread_section,
                poster=poster_text,
                published_at=published_at,
                content=content_text,
                raw_content=str(post),
                post_media=media["href"] if media and media.has_attr("href") else None,
                post_id=post_id,
                is_op=is_op,
            )

        except Exception as e:
            logging.error(f"Error while scraping post: {str(e)}")
            return None
        
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
    
    def scrape(self, url, idpost):
        self.driver.get(url)
        time.sleep(10)
        
        soup = self._get_body_html()
        last_page = self._get_last_page_number(soup)
        logging.info(f"total page: {last_page}")

        total = 0

        for page in range(1, last_page + 1):
            page_url = self._format_page_url(url, page)
            logging.info(f"Navigating to page: {page_url}")

            self.driver.get(page_url)
            time.sleep(15)
            posts = self._get_posts(self._get_body_html())
            
            logging.info(f"posts: {len(posts)}")

            for i, post in enumerate(posts):
                data = self._scrape_post(post, i)
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
