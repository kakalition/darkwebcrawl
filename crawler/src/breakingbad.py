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
    base_url = "http://bbzzzsvqcrqtki6umym6itiixfhni37ybtt7mkbjyxn2pgllzxf2qgyd.onion"

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
        bbad_body = self.driver.find_element_by_tag_name("body").get_attribute(
            "innerHTML"
        )
        return BeautifulSoup(bbad_body, "html.parser")

    def _get_thread_topic(self, soup):
        return soup.find("h1", {"class": "p-title-value"})

    def _get_thread_section(self, soup):
        return soup.find("ul", {"class": re.compile(r"p-breadcrumbs")})

    def _get_posts(self, soup):
        parent_container = soup.find(
            "div", class_="block-body js-replyNewMessageContainer"
        )
        return parent_container.find_all("article", recursive=False)

    def _get_last_page_number(self, soup):
        pages = soup.find_all("li", class_="pageNav-page")
        last_page = pages[-1]
        return int(last_page.find("a").text)

    # ------ Utility methods for saving the data ------

    def _save_post(self, data):
        query = {"post_id": data.post_id}

        data_dict = fill_date(data.__dict__, data.post_id, self.mongodb_client)

        self.mongodb_client.upsert_document('darkweb', data_dict, query)

    # ------ Main methods to scrape the content ------

    def _scrape_post(self, post):
        try:
            poster = post.get("data-author")

            if not poster:
                poster = post.find("span", {"class": "post-name"})

            is_op = "isFirstPost" in post["class"]
            # print(is_op)
            pub_str = (
                post.find("time")
                if post.find("time")
                else post.find("div", {"class": "meta-date"})
            )
            post_content = post.find("div", {"class": "bbWrapper"})

            try:
                published_at = datetime.datetime.strptime(
                    pub_str["title"], "%b %d, %Y at %H:%M %p"
                )
            except:
                published_at = datetime.datetime.now()

            thread_topic = self._get_thread_topic(self._get_body_html())
            thread_section = self._get_thread_section(self._get_body_html())

            return DarkPost(
                website=self.base_url,
                thread_url=self.driver.current_url,
                thread_topic=thread_topic.text,
                thread_section=list(filter(None, thread_section.text.split("\n"))),
                poster=poster,
                published_at=published_at,
                content=clean_html(post_content.text),
                raw_content=str(post),
                post_media=[x["src"] for x in post_content.find_all("img")],
                post_id=post.find("li", {"class": "u-concealed"}).find("a")["href"],
                is_op=is_op,
            )

        except Exception as e:
            logging.error(f"Error while scraping post: {e}")
            return None

    def scrape(self, url):
        self.driver.get(self.base_url)
        time.sleep(10)
        self.driver.get(url)
        time.sleep(15)

        soup = self._get_body_html()
        last_page = self._get_last_page_number(soup)
        total = 0

        for page in range(last_page):
            page_url = url + f"/page-{page + 1}"
            logging.info(f"Navigating to page: {page_url}")

            self.driver.get(page_url)
            time.sleep(15)

            posts = self._get_posts(self._get_body_html())
            for post in posts:
                data = self._scrape_post(post)
                if data:
                    logging.info(f"Saving post: {data.post_id}")
                    self._save_post(data)
                    total += 1
                    logging.info(f"Total posts: {total}")

        logging.info(f"Total posts scraped: {total}")

    def run(self, url):
        logging.info(f"Starting the scraper for {url}")
        time.sleep(5)
        self.scrape(url)
        logging.info(f"Scraping finished for {url}!")
