import logging
import re
import time
import traceback
from bs4 import BeautifulSoup

from config import(
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
    base_url = "https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/"

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
        username_find = soup.find("div", class_="b-userinfo__details")
        if username_find is not None:
            username_div = username_find.find("div", class_="author h-text-size--14")
            if username_div is not None:
                username_strong = username_div.find("strong")
                if username_strong is not None:
                    username_a = username_strong.find("a")
                    if username_a is not None:
                        username_span = username_a.find("span", itemprop="name").text.strip()
                        return username_span
                    else:
                        return None

    def _get_member_detail(self, soup):
        user_title = None
        date_joined_fix = None
        
        user_info = soup.find("div", class_="b-userinfo__details")
        if user_info is not None:
            user_title = user_info.find("div", class_= "usertitle").text.strip()
           
        
        date_joined_div = soup.find("div", class_="b-userinfo__details")
        if date_joined_div is not None:
            date_joined_find = date_joined_div.find("ul", class_="b-userinfo__additional-info-block h-margin-top-xl")
            if date_joined_find is not None:
                date_joined_get = date_joined_find.find_all("li", class_="b-userinfo__additional-info")
                if len(date_joined_get) > 1:  
                    date_joined_fix = date_joined_get[0].find("span").text.strip()
                    
        additional_div = soup.find("div", class_="b-userinfo__details")
        if additional_div is not None:
            additional_find = additional_div.find("ul", class_="b-userinfo__additional-info-block h-margin-top-xl")
            if additional_find is not None:
                additional_get = additional_find.find_all("li", class_="b-userinfo__additional-info")
                if len(additional_get) > 1:  
                    additional_fix_label = additional_get[1].find("label")
                    additional_fix_span = additional_get[1].find("span")
                    
                additional = f"{additional_fix_label.text.strip()} {additional_fix_span.text.strip()}" if additional_fix_label and additional_fix_span else None
                
        return user_title,date_joined_fix, additional
    

    def _get_posts(self, soup):
        try:
            # logging.info("Attempting to find posts container...")
            parent_container = soup.find('ul', attrs={"class": "conversation-list list-container h-clearfix thread-view"})
            
            if not parent_container:
                # logging.warning("Main container not found, trying alternative class...")
                parent_container = soup.find('ul', class_="conversation-list")
            
            if parent_container:
                posts = parent_container.find_all('li', recursive=False)
                # logging.info(f"Found {len(posts)} posts")
                return posts
            else:
                # logging.error("Could not find posts container")
                return []
        except Exception as e:
            logging.error(f"Error in _get_posts: {e}")
            return []
        
    def _get_all_page_numbers(self, soup):
        parent_container = None
        page_numbers = []

        parent_container_find = soup.find("div", class_="pagenav-container h-clearfix noselect")
        # print(f"Parent container_find found: {parent_container_find}")
        if parent_container_find is not None:
            parent_container = parent_container_find.find("div", class_="js-pagenav pagenav h-right js-shrink-event-parent")
            # print(f"Parent container found: {parent_container}")

        if parent_container is not None:
            # Find all <a> tags in the pagination container
            all_pagination = parent_container.find_all("a")
            # print(f"All pagination links found: {all_pagination}")

            # Iterate over all <a> tags and extract the page numbers
            for link in all_pagination:
                page_text = link.text.strip()
                # print(f"Checking page number: {page_text}")
                if page_text.isdigit():
                    page_numbers.append(int(page_text))
                    # print(f"Added page number: {page_text}")

        # Get the maximum page number from the list
        if page_numbers:
            print(f"All page numbers found: {page_numbers}")
            return page_numbers
        else:
            print("No other pages found, defaulting to page 1")
            return [1]  # Default to 1 page if no other pages are found
    
    # def _get_followers_following(self, soup):
    #     followers_el = None
    #     following_el = None
    #     try:
    #         followers_el = self.driver.find_elements_by_xpath(
    #             "/html/body/div[5]/div[1]/main/div[1]/div/div[3]/div[1]/div/div[2]/ul/li[2]/a/span")
    #         following_el = self.driver.find_elements_by_xpath(
    #             "/html/body/div[5]/div[1]/main/div[1]/div/div[3]/div[1]/div/div[2]/ul/li[1]/a/span")
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
        avatar_find = soup.find("a", {"class": "avatar large b-avatar b-avatar--l b-avatar--thread"})
        if avatar_find is not None:
            avatar_path = avatar_find.find('img')['src']
            # Menghilangkan titik di depan path jika ada
            if avatar_path.startswith('.'):
                avatar_path = avatar_path[1:]
            # Menggabungkan base URL dengan path avatar
            avatar_url = self.base_url.rstrip('/') + avatar_path
            return avatar_url
        else:
            return None
           
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

    #     print(distinct_docs)

    #     profile_urls = []
    #     for doc in distinct_docs:
    #         raw_content = self.mongodb_client.find_one(
    #             'darkweb', {'poster': doc}, {'raw_content': 1, '_id': 0})
    #         raw_content_bs = BeautifulSoup(raw_content['raw_content'], "html.parser")
    #         profile_url = raw_content_bs.find('a',  itemprop='url')['href']
    #         profile_urls.append(profile_url)

    #     return profile_urls

    # ------ Main methods to scrape the content ------

    def _scrape_post(self, post):
        try:
            username = self._get_member_username(post)
            user_title, date_joined, additional = self._get_member_detail(post)
            avatars = self._get_avatars(post)
            # messages, reaction_score, points = self._get_member_stats(post)
            # followers, following = self._get_followers_following(post)

            return DarkProfile(
                website=self.base_url,
                username=username,
                user_title=user_title,
                date_joined=date_joined,
                last_seen="-",
                messages="-",
                reaction_score= "-",
                points= "-",
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
        self.driver.get(url)
        time.sleep(10)

        soup = self._get_body_html()
        all_page_numbers = self._get_all_page_numbers(soup)

        for page_number in all_page_numbers:
            page_url = url + f'/page{page_number}'
            logging.info(f'Navigating to page: {page_url}')

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
