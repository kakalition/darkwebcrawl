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
from src.base import BaseCrawler, DarkProfile
from src.mongo import MongoDBClient
from src.selenium_config import SeleniumConfig
from utils import fill_date_profile

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

    def _get_member_header(self, soup):
        return soup.find("div", {"class": "memberHeader-content"})

    def _get_member_username(self, soup):
        return soup.find("h1", {"class": "memberHeader-name"})

    def _get_member_detail(self, soup):
        # detail = soup.find_all("div", {"class": "memberHeader-blurb"})
        user_title = soup.find("span", {"class": "userTitle"})
        date_joined = soup.find("dl", {"class": "pairs pairs--inline"}).find("dd")
        last_seen = soup.find("dl", {"class": "pairs pairs--inline"}).find("dd")
        user_title = re.sub(r'\s+', '', user_title.text) if user_title else ""
        date_joined = re.sub(r'\s+', '', date_joined.text) if date_joined else ""
        last_seen = re.sub(r'\s+', '', last_seen.text) if last_seen else ""
        return user_title, date_joined, last_seen

    def _get_member_stats(self, soup):
        stats = soup.find_all("dl", {"class": re.compile(r"pairs pairs--rows")})
        messages = stats[0].find("dd")
        reaction_score = stats[1].find("dd")
        points = stats[2].find("dd")
        return messages, reaction_score, points

    def _get_followers_following(self, soup):
        followers_el = None
        following_el = None
        try:
            followers_el = self.driver.find_elements_by_xpath(
                "//span[@class='block-footer-counter' \
                    and contains(text(), 'follower')]")
            following_el = self.driver.find_elements_by_xpath(
                "//span[@class='block-footer-counter' \
                    and contains(text(), 'following')]")
        except Exception as e:
            logging.error(f"Error while scraping followers/following: {e}")
            followers_el = 0
            following_el = 0

        followers = 0 if len(followers_el) == 0 else followers_el[0].text \
            .replace(" followers", "").replace("Total: ", "")
        following = 0 if len(following_el) == 0 else following_el[0].text \
            .replace(" following", "").replace("Total: ", "")
        return followers, following

    def _get_avatars(self, soup):
        avatar = soup.find("a", {"href": re.compile(r"/data/avatars")})
        if avatar is None:
            return ""
        else:
            re.sub(r'\s+', '', self.base_url + avatar["href"])

    # ------ Utility methods for saving the data ------

    def _save_post(self, data):
        query = {"website": data.website, "username": data.username}

        data_dict = fill_date_profile(
            data.__dict__, data.username, data.website, self.mongodb_client)

        self.mongodb_client.upsert_document('darkweb_profiles', data_dict, query)

    def _get_distinct_usernames(self, data):
        query = {"thread_url": data['thread_url']}

        docs = self.mongodb_client.find_document('darkweb', query, 'poster')
        distinct_docs = list(docs)

        profile_urls = []
        for doc in distinct_docs:
            raw_content = self.mongodb_client.find_one(
                'darkweb', {'poster': doc}, {'raw_content': 1, '_id': 0})
            raw_content_bs = BeautifulSoup(raw_content['raw_content'], "html.parser")
            profile_url = raw_content_bs.find("a", {"class": re.compile(r"avatar")})
            profile_urls.append(profile_url['href'])

        return profile_urls

    # ------ Main methods to scrape the content ------

    def _scrape_post(self, post):
        try:
            username = self._get_member_username(post)
            user_title, date_joined, last_seen = self._get_member_detail(post)
            messages, reaction_score, points = self._get_member_stats(post)
            followers, following = self._get_followers_following(post)
            avatar = self._get_avatars(post)

            return DarkProfile(
                website=self.base_url,
                username=re.sub(r'\s+', '', username.text),
                user_title=user_title,
                date_joined=date_joined,
                last_seen=last_seen,
                messages=re.sub(r'\s+', '', messages.text),
                reaction_score=re.sub(r'\s+', '', reaction_score.text),
                points=re.sub(r'\s+', '', points.text),
                followers=followers,
                following=following,
                avatar=avatar,
            )

        except Exception as e:
            logging.error(f"Error while scraping post: {traceback.format_exc()}")
            logging.error(f"Error while scraping post: {e}")
            return None

    def scrape(self, url):
        self.driver.get(self.base_url)
        time.sleep(10)

        usernames = self._get_distinct_usernames({"thread_url": url})
        logging.info(f"{len(usernames)} profiles will be scraped from {url} thread")

        for user in usernames:
            user_url = self.base_url + user
            logging.info(f"Scraping profile for {user}")
            self.driver.get(user_url)
            time.sleep(15)
            soup = self._get_body_html()
            data = self._scrape_post(soup)
            if data:
                logging.info(f"Saving post: {data.website, data.username}")
                self._save_post(data)

    def run(self, url):
        logging.info(f"Starting the scraper for {url}")
        time.sleep(5)
        self.scrape(url)
        logging.info(f"Scraping finished for {url}!")
