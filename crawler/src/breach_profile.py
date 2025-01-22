import logging
import selenium_utils
import re
import sys
import time
import traceback
from pymongo import MongoClient
from bson.objectid import ObjectId

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
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s"
)

class DarkwebCrawler(BaseCrawler):
    base_url = "http://breached26tezcofqla4adzyn22notfqwcac7gpbrleg4usehljwkgqd.onion"

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

    # ------ Utility methods for parsing the web page ------

    def _get_body_html(self):
        bbad_body = self.driver.find_element_by_tag_name("body").get_attribute(
            "innerHTML"
        )
        return BeautifulSoup(bbad_body, "html.parser")

    def _get_member_username(self, soup):
        username_find = soup.find("div", class_="post__user-profile largetext")
        if username_find is not None:
            username_a = username_find.find("a")
            if username_a:
                username_span = username_a.find("span")
                if username_span:
                    username = username_span.text.strip()
        return username

    def _get_member_detail(self, soup):
        # Ambil user title
        user_title_div = soup.find("div", {"class": "post__user-title"})
        if user_title_div:
            user_title = user_title_div.text.strip()
        else:
            user_title = "User Title Not Found"
        
        # Ambil date joined
        date_joined_find = soup.find("div", class_="post__author-stats")
        if date_joined_find is not None:
            stats_bits = date_joined_find.find_all("div", class_="post__stats-bit group")
            if len(stats_bits) >= 3:
                span = stats_bits[2].find("span", class_="float_right")
                if span is not None:
                    date_joined = span.text.strip()
                else:
                    date_joined = None
                    
        additional_find = soup.find("div", class_="post__author-stats")
        if additional_find is not None:
            additional_bits = additional_find.find_all("div", class_="post__stats-bit group")
            if len(additional_bits) >= 3:
                
                additional_texts = [f"{bit.find('span', class_='float_left').text.strip()} {bit.find('span', class_='float_right').text.strip()}" 
                            for bit in [additional_bits[0], additional_bits[1], additional_bits[3]] 
                            if bit.find('span', class_='float_left') and bit.find('span', class_='float_right')]
                
                additional = ' '.join(additional_texts) if additional_texts else None
                    
                return user_title, date_joined, additional
        
    def _get_avatars(self, soup):
        img_tag = None
        author_info = soup.find("div", class_="post__author-info")
        if author_info is not None:
            avatar_find = author_info.find("div", class_="post__user")
            if avatar_find is not None:
                avtr_all = avatar_find.find_all("a")
                if len(avtr_all) > 1:  # pastikan ada minimal 2 tag a
                    avtr = avtr_all[1]  # ambil tag a kedua
                    if avtr is not None:
                        img = avtr.find("img")
                        if img and img.get('src'):
                            img_tag = img['src']
        return img_tag
            
    def _get_posts(self, soup):
        posts_container = soup.find('td', id='posts_container')
        if posts_container:
            posts_div = posts_container.find('div', id='posts')
            if posts_div:
                posts = posts_div.find_all('div', class_='post')
                if posts:
                    return posts
        return []
    
    def _get_last_page_number(self, soup):
        parent_container = soup.find(
            "div", class_="pagination"
        )
        total = 1  # Default to 1 page
        
        if parent_container:  # Only try pagination methods if container exists
            try:
                # First, try to get total pages from pagination text
                get_total = parent_container.find('span', class_="pages").text
                match = re.search(r'\((\d+)\)', get_total)
                if match:
                    total = int(match.group(1))
            except Exception as e:
                try:
                    # Try to find last page number in pagination links
                    last_page = parent_container.find("a", class_="pagination_last").text
                    if last_page:
                        total = int(last_page)
                except Exception as e:
                    # If both methods fail, default to 1 page
                    total = 1
        
        return total
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
    #         profile_url = raw_content_bs.find("div", class_="post__user-profile largetext")
    #         profile_urls.append(profile_url.find("a")["href"])

    #     return profile_urls

    # ------ Main methods to scrape the content ------

    def _scrape_post(self, post):
        try:    
            username = self._get_member_username(post)
            user_title, date_joined, additional = self._get_member_detail(post)
            avatars = self._get_avatars(post)

            return DarkProfile(
                website=self.base_url,
                username=username,
                user_title=user_title,
                date_joined=date_joined,
                last_seen="-",
                messages="-",
                reaction_score="-",
                points="-",
                followers="-",
                following="-",
                avatar=avatars,
                additional=additional
            )

        except Exception as e:
            logging.error(f"Error while scraping post: {traceback.format_exc()}")
            logging.error(f"Error while scraping post: {e}")
            return None

    def scrape(self, url, idpost):
        window_opened = False

        try:
            self.driver.get(self.base_url)
            while True:
                try:
                    element = WebDriverWait(self.driver, 10).until(
                        EC.visibility_of_element_located((By.XPATH, "/html/body/div/div[2]/form/div[1]"))
                    )

                    logging.info(f"Wait captcha is ready")

                    if not window_opened:
                        selenium_utils.bring_window_to_front(self.driver)
                        window_opened = True

                except Exception as e:
                    print("No captcha")
                    self.driver.get(url)
                    break
                time.sleep(1)
                
            self.driver.minimize_window()
            # Check for thank you page/captcha failure
            try:
                thank_you = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.TAG_NAME, "h1"))
                )
                if "thank" in thank_you.text.lower():
                    print("Detected thank you page - captcha likely failed")
                    return None
            except:
                pass

            soup = self._get_body_html()
            if not soup:
                print("Failed to get page HTML")
                return None

            last_page = self._get_last_page_number(soup)
            if not last_page:
                print("Failed to get last page number")
                return None
                
            logging.info(f"total page: {last_page}")

            for page in range(int(last_page)):
                page_url = url + f"?page={page+1}"
                logging.info(f"Navigating to page: {page_url}")

                self.driver.get(page_url)
                time.sleep(15)
                
                # Check for captcha/thank you page on each pagination
                try:
                    thank_you = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.TAG_NAME, "h1"))
                    )
                    if "thank" in thank_you.text.lower():
                        print("Detected thank you page during pagination - captcha likely failed")
                        return None
                except:
                    pass

                posts = self._get_posts(self._get_body_html())
                if not posts:
                    print(f"No posts found on page {page+1}")
                    continue
                    
                logging.info(f" posts: {len(posts)}")

                for post in posts:
                    data = self._scrape_post(post)
                    if data:
                        self._save_post(data)
                        logging.info(f"data: {data}")
                        
            logging.info(f"Finished scraping. Total unique profiles saved: {self.saved_profiles}")
            return self.saved_profiles
            
        except Exception as e:
            logging.error(f"Error during scraping: {str(e)}")
            return None

    def run(self, url, idpost):
        print("Profile")
        logging.info(f"Starting the scraper for {url}")
        time.sleep(5)
        total = self.scrape(url, idpost)
        return total