import logging
import re
import time
import traceback
from bs4 import BeautifulSoup
from pymongo import MongoClient
from bson.objectid import ObjectId

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

client = MongoClient(f"mongodb://{MONGO_HOST}:{MONGO_PORT}/")
db = client['darkweb_task']
collection = db['testing']

class DarkwebCrawler(BaseCrawler):
    base_url = "http://enxx3byspwsdo446jujc52ucy2pf5urdbhqw3kbsfhlfjwmbpj5smdad.onion"

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
        bbad_body = self.driver.find_element_by_tag_name("body").get_attribute(
            "innerHTML"
        )
        return BeautifulSoup(bbad_body, "html.parser")

    # def _get_member_header(self, soup):
    #     print("ini MEMBER", soup.find("div", {"class": "memberHeader-content"}))


    def _get_member_username(self, soup):
        # Cek elemen <a> dengan kelas "noEmailName"
        try:
            no_email_element = soup.find("a", {"class": "noEmailName"})
            if no_email_element and "anonymous" not in no_email_element.text.lower():
                        return no_email_element.text.strip()
            return "-"
        except Exception as e:
            logging.error(f"Error extracting username: {str(e)}")
            return "-"

        # # Cek elemen <a> dengan kelas "linkName" dan atribut href
        # link_element = soup.find("a", {"class": "linkName", "href": True})
        # if link_element is not None:
        #     link = link_element.get("href")  # Mengambil URL dari atribut href
        #     text = link_element.text  # Mengambil teks dari elemen
        #     return link, text  # Mengembalikan tuple (link, teks)

        # Jika tidak ada elemen yang ditemukan, kembalikan "-"

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
        avatar = soup.find("a", class_="imgLink")
        print("AVATAR : "+str(avatar))
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
            profile_url = raw_content_bs.find("a", class_="imgLink")
            profile_urls.append(profile_url['href'])

        return profile_urls

    # ------ Main methods to scrape the content ------
    def _get_posts(self, soup):
        return soup.find_all("div", {"class": "postCell"})
    
    def _scrape_post(self, post, i):
        try:
            username = self._get_member_username(post)

            # print("USERNAME: " + str(username))
            
            # # Jika username adalah "Anonymous", return None
            # if "Anonymous" in username:
            #     return None
            # else:
            #     link = None
            #     # Jika username berupa tuple (link, teks)
            #     if isinstance(username, tuple):
            #         link, username_text = username  # Memisahkan link dan teks
            #     else:
            #         username_text = username  # Jika hanya teks yang ditemukan
                
            return DarkProfile(
                website=self.driver.current_url,
                username=username,  # Menggunakan teks username
                user_title="-",
                date_joined=None,
                last_seen="-",
                messages="-",
                reaction_score="-",
                points="-",
                followers="0",
                following="0",
                avatar="-",
                additional="-"  # Menambahkan link jika ada
            )
        except Exception as e:
            print(f"Error scraping post {i}: {e}")
            return None


    def scrape(self, url, idpost):
        logging.info(f"Scraping profile for {url}")
        self.driver.get(url)
        time.sleep(10)

        # usernames = self._get_distinct_usernames({"thread_url": url})
        # logging.info(f"{len(usernames)} profiles will be scraped from {url} thread")   
        # for thread in usernames:
        time.sleep(15)
        total = 0

        posts = self._get_posts(self._get_body_html())
        i =0
        for post in posts:
                data = self._scrape_post(post)
                if data:
                    self._save_post(data)
                    logging.info(f"data: {data}")

                    total += 1
                    logging.info(f"Total posts: {total}")

        logging.info(f"Total posts scraped: {total}")
        return total

    def run(self, url, idpost):
        print("Profile")
        logging.info(f"Starting the scraper for {url}")
        
        # Update status to processing
        result = collection.update_one(
            {"_id": ObjectId(idpost)},
            {"$set": {"status": '3'}}
        )
        time.sleep(5)
        total = self.scrape(url, idpost)
        logging.info(f"Scraping finished for {url}!")
        return total