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

client = MongoClient(f"mongodb://{MONGO_HOST}:{MONGO_PORT}/")
db = client['darkweb_task']
collection = db['testing']


class DarkwebCrawler(BaseCrawler):
    base_url = "http://enxx3byspwsdo446jujc52ucy2pf5urdbhqw3kbsfhlfjwmbpj5smdad.onion"

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
        endchan_body = self.driver.find_element_by_tag_name("body").get_attribute(
            "innerHTML"
        )
        return BeautifulSoup(endchan_body, "html.parser")

    def _get_thread_topic(self, soup):
        return soup.find("span", {"class": "labelSubject"})

    def _get_thread_section(self, url):
        return url.split(self.base_url)[1].split("/")[1]

    def _get_posts(self, soup):
        return soup.find_all("div", {"class": "postCell"})

    # ------ Utility methods for saving the data ------

    def _save_post(self, data):
        query = {"post_id": data.post_id}

        data_dict = fill_date(data.__dict__, data.post_id, self.mongodb_client)

        self.mongodb_client.upsert_document('darkweb', data_dict, query)

    # ------ Main methods to scrape the content ------

    def _scrape_post(self, post, i):
        try:
            thread_topic = self._get_thread_topic(self._get_body_html())
            thread_section = self._get_thread_section(self.driver.current_url)

            poster = post.find("a", {"class": re.compile(r"linkName")})
            pub_str = post.find("span", {"class": "labelCreated"})
            media = post.find("a", {"class": "imgLink"})
            post_id = post.find("a", {"class": "linkQuote"})

            try:
                published_at = datetime.datetime.strptime(
                    pub_str.text, "%m/%d/%Y (%a) %H:%M:%S"
                )
            except:
                published_at = datetime.datetime.strptime(
                    pub_str.text, "%m/%d/%Y (%a) %H:%M"
                )

            return DarkPost(
                website=self.base_url,
                thread_url=self.driver.current_url,
                thread_topic=thread_topic.text,
                thread_section=thread_section,
                poster=poster.text,
                published_at=published_at,
                content=clean_html(post.find('div', {"class": "divMessage"}).text),
                raw_content=str(post),
                post_media=media["href"] if media else None,
                post_id=post_id["href"],
                is_op=True if i < 1 else False,
            )

        except Exception as e:
            logging.error(f"Error while scraping post: {e}")
            return None

    def scrape(self, url, idpost):
        self.driver.get(url)
        time.sleep(10)

        posts = self._get_posts(self._get_body_html())

        total = 0
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
        result = collection.update_one(
            {"_id": ObjectId(idpost)},
            {"$set": {"status": '3'}}  # Update fields
        )
        time.sleep(5)
        total = self.scrape(url, idpost)
        logging.info(f"Scraping finished for {url}!")
        return total
