import logging
import re
import time
import traceback
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
from src.base import BaseCrawler, DarkProfile
from src.mongo import MongoDBClient
from src.selenium_config import SeleniumConfig
from utils import fill_date_profile

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s"
)

class DarkwebCrawler(BaseCrawler):
    base_url = "http://jieq75a6uwqbj5sjzaxlnd7xwgs35audjmkk4g3gfjwosfrz7cp47xid.onion"

    def __init__(self):
        super().__init__()
        self.mongodb_client = MongoDBClient(
            host=MONGO_HOST, port=MONGO_PORT, username=MONGO_USER, password=MONGO_PASS
        )
        self.saved_profiles = 0
        self.logged_profiles = set()  # Track unique profiles that have been logged

    def init_driver(self):
        driver_config = SeleniumConfig(GECKO_DRIVER_PATH, BINARY_PATH, PROFILE_PATH)
        driver = driver_config.create_firefox_driver()
        driver.implicitly_wait(15)
        return driver

    def _get_body_html(self):
        leftychan_body = self.driver.find_element_by_tag_name("body").get_attribute(
            "innerHTML"
        )
        return BeautifulSoup(leftychan_body, "html.parser")

    def _get_member_username(self, post):
        try:
            name_element = post.find("span", class_="post-name")
            if name_element:
                return name_element.text.strip()
            return "-"
        except Exception as e:
            logging.error(f"Error extracting username: {str(e)}")
            return "-"

    def _get_avatars(self, post):
        try:
            avatar_link = post.find("a", target="_blank")
            if avatar_link and avatar_link.get('href'):
                return urljoin(self.base_url, avatar_link['href'])
            return "-"
        except Exception as e:
            logging.error(f"Error extracting avatar: {str(e)}")
            return "-"

    def _save_post(self, data):
        query = {"website": data.website, "username": data.username, "avatar": data.avatar}
        
        data_dict = fill_date_profile(
            data.__dict__, data.username, data.website, self.mongodb_client)
        
        # Create a unique identifier for the profile
        profile_id = f"{data.username}_{data.website}_{data.avatar}"
        
        # Only log if we haven't seen this profile before
        if profile_id not in self.logged_profiles:
            self.logged_profiles.add(profile_id)
            self.saved_profiles += 1
            print("\n" + "="*50)
            print(f"New Profile #{self.saved_profiles}")
            print(f"Username: {data.username}")
            print(f"Website: {data.website}")
            print(f"Avatar: {data.avatar}")
            print("="*50 + "\n")
        
        # Always save to MongoDB (upsert will handle duplicates)
        self.mongodb_client.upsert_document('darkweb_profiles', data_dict, query)

    def _get_posts(self, soup):
        try:
            posts = []
            op_posts = soup.find_all("div", class_="post-container")
            posts.extend(op_posts)
            return posts
        except Exception as e:
            logging.error(f"Error getting posts: {str(e)}")
            return []
    
    def _get_last_page_number(self, soup):
        return 1
        
    def _scrape_post(self, post, i):
        try:
            username = self._get_member_username(post)
            avatars = self._get_avatars(post)
            
            return DarkProfile(
                website=self.driver.current_url,
                username=username,
                user_title="-",
                date_joined="-",
                last_seen="-",
                messages="-",
                reaction_score="-",
                points="-",
                followers="-",
                following="-",
                avatar=avatars,
                additional="-"
            )
        except Exception as e:
            logging.error(f"Error while scraping post: {traceback.format_exc()}")
            return None

    def _format_page_url(self, base_url, page):
        base_url = base_url.rstrip('/')
        if page == 1:
            return f"{base_url}"
        base_url = base_url.replace('/index.html', '')
        return f"{base_url}/{page}.html"

    def scrape(self, url, idpost):
        self.driver.get(url)
        time.sleep(10)
        
        soup = self._get_body_html()
        last_page = self._get_last_page_number(soup)
        logging.info(f"Starting scraping of {last_page} pages")

        for page in range(1, last_page + 1):
            page_url = self._format_page_url(url, page)
            self.driver.get(page_url)
            time.sleep(15)

            soup = self._get_body_html()
            posts = self._get_posts(soup)

            for i, post in enumerate(posts):
                data = self._scrape_post(post, i)
                if data:
                    self._save_post(data)
                    logging.info(f"data: {data}")

        logging.info(f"Finished scraping. Total unique profiles saved: {self.saved_profiles}")
        return self.saved_profiles

    def run(self, url, idpost):
        print("Profile")
        logging.info(f"Starting the scraper for {url}")
        time.sleep(5)
        total = self.scrape(url, idpost)
        logging.info(f"Scraping finished for {url}!")
        return total