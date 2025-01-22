import logging
import selenium_utils
import re
import sys
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
from utils import clean_html, fill_date_profile
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s"
)


class DarkwebCrawler(BaseCrawler):
    base_url = "http://pitchprash4aqilfr7sbmuwve3pnkpylqwxjbj2q5o4szcfeea6d27yd.onion"

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
        username_div = soup.find("div", style="font-size:16px;font-weight:bold;")
        if username_div is not None:
            # Mencari elemen <a> di dalam div tersebut dengan href yang diawali dengan "/@"
            username_find = username_div.find("a", href=lambda x: x and x.startswith("/@"))
            if username_find is not None:
                username = username_find.get_text(strip=True)
                return username
        return None
        # # Cari elemen <a> dengan href yang diawali "/@"
        # username_element = soup.find("a", href=lambda x: x and x.startswith("/@"))
        # if username_element is not None:
        #     username_text = username_element.get_text(strip=True)  # Hanya ambil teks
        #     # print(username_text)  # Debug: Cetak teks
        #     return username_text    
        # else:
        #     return None
        
    def _get_member_detail(self, soup):
        # Inisialisasi variabel
        user_title = None
        date_joined = None

        # Mencari elemen dengan atribut style tertentu untuk user title
        user_title_div = soup.find("div", style="font-size:16px;font-weight:bold;")
        if user_title_div is not None:
            user_title_find = user_title_div.find("a", href=lambda x: x and x.startswith("/@"))
            if user_title_find is not None:
                user_title = user_title_find.get_text(strip=True)  # Ambil teks

        # Mencari elemen untuk date joined
        date_joined_find = soup.find("a", href=lambda x: x and x.startswith("/@"))
        if date_joined_find is not None:
            date_joined_text = date_joined_find.get_text(strip=True)  # Ambil teks
            # Gunakan regex untuk mencari pola "Joined ..." di dalam teks
            match = re.search(r"Joined\s(.+)$", date_joined_text)
            if match:
                date_joined = match.group(1)  # Ambil bagian setelah "Joined"

        # Mengembalikan hasil
        return user_title, date_joined
        # last_seen = soup.find_all("div", {"class": "profile-info-item"})[0]
        # user_title = re.sub(r'\s+', '', user_title.text) if user_title else ""
        # date_joined = re.sub(r'\s+', '', date_joined.text) if date_joined else ""
        # last_seen = re.sub(r'\s+', '', last_seen.text) if last_seen else ""
           
    
    def _get_followers(self, soup):
        followers_find = soup.find("div", style="display:block;margin-top:5px;font-size:14px;color:grey;")
        if followers_find is not None:
            # Gunakan select_one untuk memilih b:first-of-type atau b:nth-of-type(1)
            followers = followers_find.select_one("b:first-of-type")
            
            if followers is not None:
                # Gunakan get_text(strip=True) untuk mendapatkan teks dan menghapus whitespace
                follow = followers.get_text(strip=True)
                return follow
        
        return None

    def _get_avatars(self, soup):
        avatar = soup.find("span", class_="hoverShow")
        if avatar is None:
            return ""
        avatar_link = avatar.find("img", class_="avatar")['src']
        return avatar_link
        
    def _get_posts(self, soup):
        # Temukan semua elemen dengan class 'mContent'
        parent_divs = soup.find_all('div', class_='mContent')
        
        # Untuk setiap elemen parent, ambil elemen anaknya (kecuali pertama dan terakhir)
        result = []
        for parent in parent_divs:
            child_divs = parent.find_all('div', recursive=False)  # Ambil hanya elemen langsung (non-recursive)
            if len(child_divs) > 2:  # Pastikan ada cukup elemen untuk skip
                skipped_divs = child_divs[1:-1]  # Skip elemen pertama dan terakhir  
                result.extend(skipped_divs)  # Tambahkan hasil yang di-skip ke result\
                    
        return result


    def _get_last_page_number(self, soup):
        parent_container = soup.find("div", class_="pagination")
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

    # ------ Main methods to scrape the content ------

   
    def _scrape_post(self, post):
        try:

        # Clean raw_content and content
            # def clean_content(content):
            #     # Remove extra newlines
            #     content = re.sub(r'\n+', ' ', content)
                
            #     # Remove HTML tags
            #     content = re.sub(r'<[^>]+>', '', content)
                
            #     # Remove extra whitespaces
            #     content = re.sub(r'\s+', ' ', content).strip()
                
                # return content
            username = self._get_member_username(post)
            user_title ,date_joined= self._get_member_detail(post)
            followers = self._get_followers(post)
            avatars = self._get_avatars(post)
            
            
            return DarkProfile(
                website=self.base_url,
                username=username,
                user_title=user_title,
                date_joined=date_joined,
                last_seen='-',
                messages='-',
                reaction_score= '-',
                points= '-',
                followers=followers,
                following="-",
                avatar=avatars,
                additional=None
            )
            
        except Exception as e:
            logging.error(f"Error while scraping post: {traceback.format_exc()}")
            logging.error(f"Error while scraping post: {e}")
            return None

    def scrape(self, url, idpost):
        window_opened = False

        self.driver.get(self.base_url)

        while True:
            try:
                element = WebDriverWait(self.driver, 10).until(
                    EC.visibility_of_element_located((By.XPATH, "/html/body/div/div/div[4]"))
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
        soup = self._get_body_html()
       
        last_page = self._get_last_page_number(soup)
        logging.info(f"total page: {last_page}")

        for page in range(int(last_page)):
            page_url = url + f"?p={page+1}"
            logging.info(f"Navigating to page: {page_url}")

            self.driver.get(page_url)
            time.sleep(15)

            posts = self._get_posts(self._get_body_html())
            
           
            logging.info(f" posts: {len(posts)}")

            for post in posts:
                data = self._scrape_post(post)
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
