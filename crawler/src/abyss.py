import datetime
import logging
import re
import time

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

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s"
)


class DarkwebCrawler(BaseCrawler):
    base_url = "http://qyvjopwdgjq52ehsx6paonv2ophy3p4ivfkul4svcaw6qxlzsaboyjid.onion"

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
        abyss_body = self.driver.find_element_by_tag_name("body").get_attribute(
            "innerHTML"
        )
        return BeautifulSoup(abyss_body, "html.parser")

    def _get_thread_topic(self, soup):
        return soup.find("h2", {"class": "topic-title"})

    def _get_thread_section(self, soup):
        return soup.find_all("li", {"class": "breadcrumbs", "itemscope": ""})[2]

    def _get_posts(self, soup):
        return soup.find_all("div", {"class": re.compile(r"has-profile")})

    # ------ Utility methods for saving the data ------

    def _save_post(self, data):
        query = {"post_id": data.post_id}

        data_dict = fill_date(data.__dict__, data.post_id, self.mongodb_client)

        self.mongodb_client.upsert_document("darkweb", data_dict, query)

    # ------ Main methods to scrape the content ------

    def _scrape_post(self, post, i):
        try:
            thread_topic = self._get_thread_topic(self._get_body_html())
            thread_section = self._get_thread_section(self._get_body_html())

            poster = post.find("a", {"class": "username"})
            pub_str = (
                post.find("time")
                if post.find("time")
                else post.find("div", {"class": "meta-date"})
            )
            post_content = post.find("div", {"class": "content"})

            published_at = (
                datetime.datetime.strptime(pub_str.text, "%a %b %d, %Y %H:%M %p")
                if "hour" not in pub_str.text
                else datetime.datetime.now()
                + datetime.timedelta(hours=int(pub_str.text.split(" hour")[0]))
            )

            return DarkPost(
                website=self.base_url,
                thread_url=self.driver.current_url,
                thread_topic=thread_topic.text,
                thread_section=list(filter(None, thread_section.text.split("\n"))),
                poster=poster.text,
                published_at=published_at,
                content=clean_html(post_content.text),
                raw_content=str(post),
                post_media=[x["src"] for x in post_content.find_all("img")],
                post_id=post.find("div", {"id": re.compile(r"post_content")}).find("a")[
                    "href"
                ],
                is_op=True if i < 1 else False,
            )

        except Exception as e:
            logging.error(f"Error while scraping post: {e}")
            return None

    def scrape(self, url):
        self.driver.get(self.base_url)
        time.sleep(10)

        self.driver.get(url)
        time.sleep(10)

        posts = self._get_posts(self._get_body_html())

        total = 0
        for i, post in enumerate(posts):
            data = self._scrape_post(post, i)
            if data:
                logging.info(f"Saving post: {data.post_id}")
                self._save_post(data)

                total += 1

        logging.info(f"Total posts scraped: {total}")

    def run(self, url):
        logging.info(f"Starting the scraper for {url}")
        time.sleep(7)
        self.scrape(url)
        logging.info(f"Scraping finished for {url}!")
