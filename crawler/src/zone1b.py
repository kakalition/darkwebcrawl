import datetime
import logging
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
from src.base import BaseCrawler
from src.mongo import MongoDBClient
from src.selenium_config import SeleniumConfig
from utils import clean_html, fill_date

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s"
)


class DarkwebCrawler(BaseCrawler):
    base_url = "http://zone1b.com"

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

    # ----- Utility methods for parsing the web page -----

    def _get_forum_type(self, driver):
        try:
            forum_type = driver.find_element_by_xpath(
                "//li[@itemprop='itemListElement'][last()]/a/span"
            ).text
            return forum_type
        except Exception as e:
            logging.error(f"Error happened on getting the forum type {e}")
            return None

    def _get_role(self, driver):
        try:
            role = driver.find_element_by_xpath("//h5[@itemprop='jobTitle']")
            return role.text
        except Exception as e:
            logging.error(f"Error happened on getting the role {e}")
            return None

    def _get_content_post(self, driver):
        try:
            content = driver.find_element_by_xpath(".//div[@class='bbWrapper']")
            content = content.get_attribute("innerHTML")
            return content
        except Exception as e:
            logging.error(f"Error happened on getting the content_post {e}")
            return None

    def _get_published_at(self, driver):
        try:
            date = driver.find_element_by_xpath(".//a[@class='u-concealed']/time")
            date = date.get_attribute("datetime")
            datetime_format = datetime.datetime.strptime(date, "%Y-%m-%dT%H:%M:%S+%f")
            return datetime_format
        except Exception as e:
            logging.error(f"Error happened on getting the published date {e}")
            return None

    def _get_badges(self, driver):
        try:
            badges = driver.find_elements_by_xpath(
                ".//article[@class='message message--post js-post js-inlineModContainer  '][1]//div[@class='message-userDetails'][1]/div[@itemprop='jobTitle']"
            )
            badges_list = []
            for b in badges:
                badges_list.append(b.text)
            return badges_list
        except Exception as e:
            logging.error(f"Error happened on getting the badges {e}")
            return None

    def _get_joined(self, driver):
        try:
            joined = driver.find_element_by_xpath(
                ".//div[@class='message-userExtras']/dl[1]/dd"
            )
            return joined.text
        except Exception as e:
            logging.error(f"Error happened on getting the joined date {e}")
            return None

    def _get_messages(self, driver):
        try:
            messages = driver.find_element_by_xpath(
                ".//div[@class='message-userExtras']/dl[2]/dd"
            )
            return int(messages.text)
        except Exception as e:
            logging.error(f"Error happened on getting the messages {e}")
            return None

    def _get_likes(self, driver):
        try:
            likes = driver.find_element_by_xpath(
                ".//div[@class='message-userExtras']/dl[3]/dd"
            )
            return int(likes.text)
        except Exception as e:
            logging.error(f"Error happened on getting the likes {e}")
            return None

    # ----- Utility methods for saving the data -----

    def _save_post(self, data):
        query = {"post_id": data["post_id"]}

        data_dict = fill_date(data.__dict__, data.post_id, self.mongodb_client)

        self.mongodb_client.upsert_document('zone1b', data_dict, query)

    # ---- Main methods to scrape the content -----

    def _scrape_post(self, post):
        try:
            title = post.find_element_by_xpath("//div[@class='p-title ']/h1").text

            forum_type = self._get_forum_type(self.driver)

            username = post.find_element_by_xpath(
                ".//span[contains(@class, 'username')]"
            )

            role = self._get_role(post)

            content = self._get_content_post(post)

            published_at = self._get_published_at(post)

            badges = self._get_badges(post)

            joined = self._get_joined(post)

            messages = self._get_messages(post)

            likes = self._get_likes(post)

            return {
                "website": self.base_url,
                "title": title,
                "forum_type": forum_type,
                "username": username.text,
                "role": role,
                "content": clean_html(content),
                "raw_content": content,
                "published_at": published_at,
                "badges": badges,
                "joined": joined,
                "messages": messages,
                "likes": likes,
            }

        except Exception as e:
            logging.error(f"Error while scraping post: {e}")
            return None

    def scrape(self, url):
        self.driver.get(url)

        time.sleep(10)

        total = 0

        logging.info(f"Saving post from URL: {url}")

        posts = self.driver.find_elements_by_xpath(
            "//article[contains(@data-content, 'post')]"
        )

        for post in posts:
            data = self._scrape_post(post)
            data["url"] = url
            data["post_id"] = url + post.get_attribute("data-content")
            total += 1
            self._save_post(data)

        logging.info(f"Total posts scraped: {total}")

    def run(self, url):
        logging.info(f"Starting the scraper for {url}")
        time.sleep(7)
        self.scrape(url)
        logging.info(f"Scraping finished for {url}!")
