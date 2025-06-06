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
    base_url = "http://leftychans5gstl4zee2ecopkv6qvzsrbikwxnejpylwcho2yvh4owad.onion"

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
    
        thread_topic = soup.find("h1", {"class": "glitch"})
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
            op_posts = soup.find_all("div", class_="post op")
            reply_posts = soup.find_all("div", class_="post reply")
            
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
        parent_container = soup.find("div", class_="pages")
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
            poster = post.find("span", {"class": re.compile(r"name")})
            poster_text = poster.text if poster else "Anonymous"

            a_tag = post.find('a', href=True, class_=None)
            media = a_tag.find("img", class_="post-image") if a_tag else None
            
            time_tag = post.find('time')
            content_div = post.find('div', {"class": "body"})
            content_text = clean_html(content_div.text) if content_div else ""
            
            # Updated post ID generation using post_op or post_reply
            post_op = post.find('div', class_='post_op')
            post_reply = post.find('div', class_='post_reply')
            
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
            
            # Parse datetime with better error handling
            published_at = "-"
            if time_tag and time_tag.has_attr('datetime'):
                datetime_str = time_tag['datetime']
                try:
                    published_at = datetime.datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%SZ")
                except ValueError as e:
                    logging.error(f"Error parsing datetime: {e}")

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