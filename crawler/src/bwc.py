import datetime
import logging
import re
import time
import traceback

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
    base_url = "http://e735q7rop3xday7y3nbguaeggl5ss6vez6rz4oxwhs3p2sqrx45vhiqd.onion/index.php?sid=2c3c4328f70c3f0249a9fb4937233623"

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
        endchan_body = self.driver.find_element_by_tag_name("body").get_attribute(
            "innerHTML"
        )
        return BeautifulSoup(endchan_body, "html.parser")

    def _get_thread_topic(self, soup):
        return soup.find("h2", class_="topic-title").a.text

    def _get_thread_section(self, soup):
        return [
            i.text.strip()
            for i in soup.find("ul", {"id": "nav-breadcrumbs"}).find_all(
                "span", {"itemprop": "title"}
            )
        ]

    def _get_posts(self, soup):
        return soup.find_all("div", {"class": "post"})

    def _get_last_page_number(self, soup):
        try:
            pagination_div = soup.find("div", class_="pagination")

            if pagination_div:
                ul = pagination_div.find("ul")
                if ul:
                    pages = ul.find_all("li")

                    if pages:
                        last_page = pages[-2]
                        return int(last_page.text)

        except (ValueError, IndexError):
            return 1

        return 1  # Default return if no valid page number is found

    # ------ Utility methods for saving the data ------

    def _save_post(self, data):
        query = {"post_id": data.post_id}
        
        data_dict = fill_date(data.__dict__, data.post_id, self.mongodb_client)

        self.mongodb_client.upsert_document('darkweb', data_dict, query)

    # ------ Main methods to scrape the content ------

    def _scrape_post(self, post, i):
        try:
            thread_topic = self._get_thread_topic(self._get_body_html())
            thread_section = self._get_thread_section(self._get_body_html())

            poster = post.find("a", class_="username-coloured").text
            pub_str = post.find("p", class_="author").text.split("»")[1].strip()
            post_id = (
                self.driver.current_url
                + post.find("div", class_="postbody").h3.a["href"]
            )
            content = post.find("div", class_="content").text
            # print(content)

            try:
                published_at = datetime.datetime.strptime(
                    pub_str, "%a %b %d, %Y %I:%M %p"
                )
            except ValueError:
                published_at = datetime.datetime.now()

            return DarkPost(
                website=self.base_url,
                thread_url=self.driver.current_url,
                thread_topic=thread_topic,
                thread_section=thread_section,
                poster=poster,
                published_at=published_at,
                content=clean_html(content),
                raw_content=str(post),
                post_media=None,
                post_id=post_id,
                is_op=True if i < 1 else False,
            )

        except Exception as e:
            traceback.print_exc()
            logging.error(f"Error while scraping post: {e}")
            return None

    def scrape(self, url):
        self.driver.get(self.base_url)
        time.sleep(10)
        self.driver.get(url)
        time.sleep(15)

        soup = self._get_body_html()
        last_page = self._get_last_page_number(soup)
        # print("ini jumlah halaman:",last_page)
        total = 0

        for page in range(last_page):
            page_url = url + f"&start={page * 10}"
            logging.info(f"Navigating to page: {page_url}")

            self.driver.get(page_url)
            time.sleep(15)

            posts = self._get_posts(self._get_body_html())
            for i, post in enumerate(posts):
                data = self._scrape_post(post, i)
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
