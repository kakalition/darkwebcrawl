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
    base_url = "http://oniongunutp6jfdhkgvsaucuunp4b7kqmbeeo5nxbxtnfxptlaxotmid.onion/"

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
        return soup.find("h2", class_="display_title").span.text

    def _get_thread_section(self, soup):
        section_values = [
            i.text.strip()
            for i in soup.find("div", {"class": "navigate_section"}).find_all("span")
        ]

        # Filter out values represented by '►'
        section_values = [value for value in section_values if value != "►"]
        return section_values
        # return [i.text.strip() for i in soup.find('div', {'class': 'navigate_section'}).find_all('span')]

    def _get_posts(self, soup):
        return soup.find("div", {"id": "forumposts"}).find_all(
            "div", {"class": "windowbg"}
        )

    def _get_last_page_number(self, soup):
        pages = soup.find("div", class_="pagelinks").find_all("a")
        last_page = pages[-2]
        return int(last_page.text)

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
            poster = post.find("div", class_="poster").h4.a.text
            post_id = post.find("a", class_="smalltext")["href"]
            content = post.find("div", class_="inner").text
            # print(post_id)

            pub_str = post.find("div", class_="postinfo").a.text
            month_translation = {
                "января": "January",
                "февраля": "February",
                "марта": "March",
                "апреля": "April",
                "мая": "May",
                "июня": "June",
                "июля": "July",
                "августа": "August",
                "сентября": "September",
                "октября": "October",
                "ноября": "November",
                "декабря": "December",
            }
            try:
                # Split the given time into components
                time_components = pub_str.split()
                # Translate the month
                translated_month = month_translation[time_components[0]]
                # Combine the translated month and the rest of the components
                formatted_date = f"{translated_month} {time_components[1].rstrip(',')}, {time_components[2].rstrip(',')}"
                formatted_time = time_components[3]
                # Combine the date and time
                combined_datetime = f"{formatted_date}, {formatted_time}"
                # Step 2: Convert the time to a 24-hour format
                datetime_obj = datetime.datetime.strptime(
                    combined_datetime, "%B %d, %Y, %H:%M"
                )
                published_at = datetime_obj.strftime("%Y-%m-%d %H:%M:%S.%f")
            except:
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
            page_url = url + f".{page * 15}"
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
