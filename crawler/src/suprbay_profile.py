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


class DarkwebCrawler(BaseCrawler):
    base_url = "http://suprbaydvdcaynfo4dgdzgxb4zuso7rftlil5yg5kqjefnw4wq4ulcad.onion"

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
        bbad_body = self.driver.find_element_by_tag_name("body").get_attribute(
            "innerHTML"
        )
        return BeautifulSoup(bbad_body, "html.parser")

    def _get_member_header(self, soup):
        return soup.find("div", {"class": "memberHeader-content"})

    def _get_member_username(self, soup):
        return soup.find("span", class_="largetext")

    def _get_member_detail(self, soup):
        user_detail = soup.find("div", class_="post_author scaleimages")
        stats_div = soup.find("div", class_="author_statistics")
        
        # Get username
        user_title = user_detail.find("span", {"class": "largetext"}).find("a")
        user_title = re.sub(r'\s+', '', user_title.text) if user_title else ""
        date_joined ='-'
        # Get last active date
        last_active_text = stats_div.text.split("<br>")[0]
        last_seen = re.sub(r'\s+', '', last_active_text.split(':')[1].replace("Threads", "").strip()) if last_active_text else "-"
        
        # Get stats
        # Get stats
        threads = stats_div.find("a", href=lambda x: "finduserthreads" in str(x)).text
        posts = stats_div.find("a", href=lambda x: "finduser" in str(x) and "finduserthreads" not in str(x)).text   
        reputation_link = stats_div.find("a", href=lambda x: "reputation.php" in str(x))
        reputation = reputation_link.find("strong", class_="reputation_positive").text if reputation_link and reputation_link.find("strong", class_="reputation_positive") else "0"
        stats_text = f"Threads: {threads} Posts: {posts} Reputation: {reputation}"
        return user_title, date_joined, last_seen, stats_text

    def _get_member_stats(self, soup):
        author_statistic = soup.find("div", "author_statistics").text.split("<br>")
        otherinfo = soup.find("div", "author_statistics").text
        messages = "-"
        reaction_score = "-"
        points = "-"
        
        stats = re.sub(r'\s+', ' ', otherinfo) if otherinfo else ""
        return messages, reaction_score, points, stats

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

    def _get_avatars(self, soup):
        avatar_div = soup.find("div", {"class": "author_avatar"})
        if avatar_div is None:
            return ""  
        avatar_link = avatar_div.find("a")
        if avatar_link is None:
            return ""  
        img_tag = avatar_link.find("img")['src']
        return img_tag
    
    # ------ Utility methods for saving the data ------
    def _get_last_page_number(self, soup):
        # Find div where class is exactly "pagination"
        parent_container = soup.find(
            lambda tag: tag.name == "div" and 
                    tag.get('class') == ["pagination"] and
                    (tag.get('style') is None or 'display: none' not in tag.get('style', ''))
        )
        
        # print("ini parent_container", parent_container)
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
    
    def _get_posts(self, soup):
        return soup.find_all('div', class_='post classic')
    
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

    def _get_distinct_usernames(self, data):
        query = {"thread_url": data['thread_url']}

        docs = self.mongodb_client.find_document('darkweb_profiles', query, 'poster')
        distinct_docs = list(docs)

        profile_urls = []
        for doc in distinct_docs:
            raw_content = self.mongodb_client.find_one(
                'test', {'poster': doc}, {'raw_content': 1, '_id': 0})
            raw_content_bs = BeautifulSoup(raw_content['raw_content'], "html.parser")
            profile = raw_content_bs.find("div", class_="author_information")
            profile_url = profile.find("span", class_="largetext")
            profile_urls.append(profile_url.find('a')["href"])

        return profile_urls

    # ------ Main methods to scrape the content ------

    def _scrape_post(self, post):
        try:
            username_extract = self._get_member_username(post)
            username = username_extract.find("a").text
            user_title, date_joined, last_seen, final_text = self._get_member_detail(post)
            messages, reaction_score, points, stats = self._get_member_stats(post)
            # print(self._get_member_stats(post))
        

            # followers, following = self._get_followers_following(post)
            img_tag = self._get_avatars(post)
            # print(self._get_avatars(post))

            return DarkProfile(
                website=self.base_url+"/"+username,
                username=username,
                user_title=user_title,
                date_joined=date_joined,
                last_seen=last_seen,
                messages=messages,
                reaction_score=reaction_score,
                points=points,
                followers="",
                following="",
                avatar=img_tag,
                additional=final_text.strip(),
            )

        except Exception as e:
            logging.error(f"Error while scraping post: {traceback.format_exc()}")
            logging.error(f"Error while scraping post: {e}")
            return None

    
    def scrape(self, url, idpost):  # Added idpost parameter
        self.driver.get(url)
        time.sleep(10)

        soup = self._get_body_html()
        last_page = self._get_last_page_number(soup)
        logging.info(f"total page: {last_page}")

        for page in range(int(last_page)):
            page_url = url + f'?page={page + 1}'
            logging.info(f'Navigating to page: {page_url}')

            self.driver.get(page_url)
            time.sleep(15)

            posts = self._get_posts(self._get_body_html())
            
            logging.info(f"posts: {len(posts)}")

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
