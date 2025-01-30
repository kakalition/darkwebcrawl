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
    base_url = "http://leftychans5gstl4zee2ecopkv6qvzsrbikwxnejpylwcho2yvh4owad.onion"

    def __init__(self):
        super().__init__()
        self.mongodb_client = MongoDBClient(
            host=MONGO_HOST, port=MONGO_PORT, username=MONGO_USER, password=MONGO_PASS, database_name="allnewdarkweb"
        )
        self.saved_profiles = 0
        self.logged_profiles = set()  # Track unique profiles that have been logged

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

    def _get_member_username(self, post):
        """Extract username from a post"""
        try:
            # Find the username directly using the specific class
            name_element = post.find("span", class_="postername")
            if name_element:
                return name_element.text.strip()
            return "-"
        except Exception as e:
            logging.error(f"Error extracting username: {str(e)}")
            return "-"

           # Mengembalikan teks dari elemen tanpa href

    # def _get_member_detail(self, soup):
    #     # detail = soup.find_all("div", {"class": "memberHeader-blurb"})
    #     user_title = soup.find("span", {"class": "subject"})
    #     date_joined = soup.find("time", {"data_local": "true"}).find("dd")
    #     last_seen = soup.find("dl", {"class": "pairs pairs--inline"}).find("dd")
    #     user_title = re.sub(r'\s+', '', user_title.text) if user_title else ""
    #     date_joined = re.sub(r'\s+', '', date_joined.text) if date_joined else ""
    #     last_seen = re.sub(r'\s+', '', last_seen.text) if last_seen else ""

    # def _get_member_stats(self, soup):
    #     stats = soup.find_all("dl", {"class": re.compile(r"pairs pairs--rows")})
    #     messages = stats[0].find("dd")
    #     reaction_score = stats[1].find("dd")
    #     points = stats[2].find("dd")
    #     return messages, reaction_score, points

    # def _get_followers_following(self, soup):
    #     followers_el = None
    #     following_el = None
    #     try:
    #         followers_el = self.driver.find_elements_by_xpath(
    #             "//span[@class='block-footer-counter' \
    #                 and contains(text(), 'follower')]")
    #         following_el = self.driver.find_elements_by_xpath(
    #             "//span[@class='block-footer-counter' \
    #                 and contains(text(), 'following')]")
    #     except Exception as e:
    #         logging.error(f"Error while scraping followers/following: {e}")
    #         followers_el = 0
    #         following_el = 0

    #     followers = 0 if len(followers_el) == 0 else followers_el[0].text \
    #         .replace(" followers", "").replace("Total: ", "")
    #     following = 0 if len(following_el) == 0 else following_el[0].text \
    #         .replace(" following", "").replace("Total: ", "")
    #     return followers, following

    # def _get_avatars(self, soup):
    #     avatar_link = soup.find("a")
    #     if avatar_link is None:
    #         return ""  
    #     img_tag = avatar_link.find("img")['src']
        # print(img_tag)
    # ------ Utility methods for saving the data ------

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
        
    # def _get_distinct_usernames(self, data):
    #     query = {"thread_url": data['thread_url']}

    #     docs = self.mongodb_client.find_document('darkweb', query, 'poster')
    #     distinct_docs = list(docs)

    #     profile_urls = []
    #     for doc in distinct_docs:
    #         raw_content = self.mongodb_client.find_one(
    #             'darkweb', {'poster': doc}, {'raw_content': 1, '_id': 0})
    #         raw_content_bs = BeautifulSoup(raw_content['raw_content'], "html.parser")
    #         profile_url = raw_content_bs.find("a", class_="imgLink")
    #         profile_urls.append(profile_url['href'])

    #     return profile_urls
    # def _get_avatars(self, post):
    #     """Extract avatar link href from post"""
    #     try:
    #         # Langsung cari tag a dengan class imgLink
    #         avatar_link = post.find("a", class_="imgLink")
    #         if avatar_link and avatar_link.get('href'):
    #             return urljoin(self.base_url, avatar_link['href'])
    #         return "-"
    #     except Exception as e:
    #         logging.error(f"Error extracting avatar: {str(e)}")
    #         return "-"
    
    # ------ Main methods to scrape the content ------
    def _get_posts(self, soup):
        """Get all posts from the page"""
        try:
            # Find all post containers
            posts = []
            # Find both original posts and replies
            op_posts = soup.find_all("div", class_="op")
            reply_posts = soup.find_all("td", class_="reply")
            
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
        parent_container = soup.find("tbody", style='display: inline-block;')
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
        
    def _scrape_post(self, post, i):
        try:
            # Extract username
            username = self._get_member_username(post)
            
            # Create profile object
            return DarkProfile(
                website=self.driver.current_url,
                username=username,  # Now it's a single string instead of a list
                user_title="-",
                date_joined="-",
                last_seen="-",
                messages="-",
                reaction_score="-",
                points="-",
                followers="-",
                following="-",
                avatar='-',
                additional="-"
            )
        except Exception as e:
            logging.error(f"Error while scraping post: {traceback.format_exc()}")
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
        # Start with the index page
        self.driver.get(url)
        time.sleep(10)
        
        soup = self._get_body_html()
        last_page = self._get_last_page_number(soup)
        logging.info(f"Total pages: {last_page}")
        
        # Iterate through pages starting from 1 (index.html) to last_page
        for page in range(1, last_page + 1):
            page_url = self._format_page_url(url, page)
            logging.info(f"Navigating to page: {page_url}")

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
