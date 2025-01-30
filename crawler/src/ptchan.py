import datetime
import logging
import re
import time
from bs4 import BeautifulSoup
from pymongo import MongoClient
from bson.objectid import ObjectId
from urllib.parse import urljoin

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
    base_url = "http://jieq75a6uwqbj5sjzaxlnd7xwgs35audjmkk4g3gfjwosfrz7cp47xid.onion"

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
    
        thread_topic = soup.find("h1", {"class": "board-title"})
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
            op_posts = soup.find_all("div", class_="post-container")
            
            # Combine both types of posts
            posts.extend(op_posts)
            
            logging.info(f"Found {len(posts)} posts")
            return posts
        except Exception as e:
            logging.error(f"Error getting posts: {str(e)}")
            return []

    # ------ Utility methods for saving the data ------
    def _get_last_page_number(self, soup):
        """
        Returns default page number of 1
        """
        return 1
    
    def _get_post_media(self, post):
        """Extract avatar link href from post"""
        try:
            # Langsung cari tag a dengan class imgLink
            avatar_link = post.find("a", target="_blank")
            if avatar_link and avatar_link.get('href'):
                return urljoin(self.base_url, avatar_link['href'])
            return "-"
        except Exception as e:
            logging.error(f"Error extracting avatar: {str(e)}")
            return "-"

# Remove the _format_page_url method since it won't be needed
        
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
            post_media = self._get_post_media(post)
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
            poster = post.find("span", {"class": re.compile(r"post-name")})
            poster_text = poster.text if poster else "Anonymous"

            published_at = None  # Set default value
            timestamp_text = post.find('time', class_="post-date reltime")
            if timestamp_text:
                # Get the datetime attribute directly
                datetime_str = timestamp_text.get('datetime')
                try:
                    # Parse the ISO format datetime
                    published_at = datetime.datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                    print("Publication date:", published_at)
                except ValueError as e:
                    logging.error(f"Error parsing datetime: {e}")
                    published_at = None
                
            media = post.find('a', href=True, class_='imgLink')
            
            time_tag = post.find('time')
            content_div = post.find('pre', {"class": "post-message"})
            content_text = clean_html(content_div.text) if content_div else ""
            
            # Updated post ID generation using post_op or post_reply
            post_op = post.find('div', class_='post-container op')
            post_reply = post.find('div', class_='post-container')
            
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
                post_media=post_media,
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
        total = 0

        # Loop through each page
        soup = self._get_body_html()
        last_page = self._get_last_page_number(soup)
        logging.info(f"Total pages: {last_page}")

        for page in range(1, last_page + 1):
            page_url = self._format_page_url(url, page)
            logging.info(f"Navigating to page: {page_url}")

            # Navigate to the page
            self.driver.get(page_url)
            time.sleep(10)

            # Get posts from the current page
            posts = self._get_posts(self._get_body_html())
            logging.info(f"Posts found: {len(posts)}")

            for i, post in enumerate(posts):
                data = self._scrape_post(post, i)
                if data:
                    logging.info(f"Saving post: {data.post_id}")
                    self._save_post(data)
                    logging.info(f"Data saved: {data}")
                    total += 1
                    logging.info(f"Total posts scraped so far: {total}")

            # Close and quit the current driver instance
            logging.info(f"Closing current page: {page_url}")
            self.driver.quit()  # Ensure the driver is completely closed
            self.driver = None  # Reset the driver instance to ensure it's not reused

            # Reinitialize the driver only if there are more pages
            if page < last_page:
                logging.info("Reinitializing the driver for the next page")
                self.driver = self.init_driver()

        logging.info(f"Total posts scraped: {total}")
        return total
    
    def run(self, url, idpost):
        print("Post")
        logging.info(f"Starting the scraper for {url}")
        time.sleep(5)
        total = self.scrape(url, idpost)
        logging.info(f"Scraping finished for {url}!")
        return total
