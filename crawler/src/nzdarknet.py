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
    base_url = "http://nzdnmfcf2z5pd3vwfyfy3jhwoubv6qnumdglspqhurqnuvr52khatdad.onion/index.php"

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
        return soup.find("ul", {"class": "crumbs"}).find_all("a")[-1].text

    def _get_thread_section(self, soup):
        return [
            i.text.strip() for i in soup.find("ul", {"class": "crumbs"}).find_all("a")
        ]

    def _get_posts(self, soup):
        return soup.find("div", {"id": "brdmain"}).find_all(
            "div", {"class": "blockpost"}
        )

    def _get_last_page_number(self, soup):
        try:
            pages = soup.find("p", class_="pagelink").find_all("a")
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

    def _scrape_post(self, post):
        try:
            thread_topic = self._get_thread_topic(self._get_body_html())
            thread_section = self._get_thread_section(self._get_body_html())

            is_op = "firstpost" in post["class"]
            poster = post.find("div", class_="postleft").find("a").text
            pub_str = post.find("h2").a.text
            post_id = self.driver.current_url + post.find("h2").a["href"]
            post_content = post.find("div", {"class": "postmsg"}).find_all("p")
            for p_tag in post_content:
                content = p_tag.text
            print(is_op)

            try:
                published_at = datetime.datetime.strptime(
                    pub_str, "%a %b %d, %Y %I:%M %p"
                )
            except ValueError:
                published_at = datetime.datetime.now()
            # print(post_id)

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
                is_op=is_op,
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
            page_url = url + f"&p={page + 1}"
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
