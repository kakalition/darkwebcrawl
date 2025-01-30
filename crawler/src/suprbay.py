import logging
import time
import re
import datetime
from bs4 import BeautifulSoup
from pymongo import MongoClient
from bson.objectid import ObjectId

from src.selenium_config import SeleniumConfig
from src.base import DarkPost
from src.base import BaseCrawler
from src.mongo import MongoDBClient
from utils import fill_date
from config import GECKO_DRIVER_PATH, BINARY_PATH, PROFILE_PATH, MONGO_HOST, MONGO_PORT, MONGO_USER, MONGO_PASS

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(message)s')


class DarkwebCrawler(BaseCrawler):
    base_url = "http://suprbaydvdcaynfo4dgdzgxb4zuso7rftlil5yg5kqjefnw4wq4ulcad.onion"

    def __init__(self):
        super().__init__()
        self.mongodb_client = MongoDBClient(
            host=MONGO_HOST,
            port=MONGO_PORT,
            username=MONGO_USER,
            password=MONGO_PASS,
            database_name="allnewdarkweb"
        )

    def init_driver(self):
        driver_config = SeleniumConfig(GECKO_DRIVER_PATH, BINARY_PATH, PROFILE_PATH)
        driver = driver_config.create_firefox_driver()
        driver.implicitly_wait(15)
        return driver


    # ------ Utility methods for parsing the web page ------
    
    def _get_body_html(self):
        bbad_body = self.driver.find_element_by_tag_name("body").get_attribute("innerHTML")
        return BeautifulSoup(bbad_body, 'html.parser')

    def _get_thread_topic(self, soup):
        return soup.find('span', {"class": "active"})

    def _get_thread_section(self, soup):
        navget = soup.find('div', class_= re.compile(r"navigation"))
        listthread = []
        for lh in navget.find_all('a'):

            listthread.append(lh.text)
        # return listthread
        return listthread

    def _get_posts(self, soup):
        # parent_container = soup.find('ul', class_='conversation-list')
        parent_container = soup.find('table', class_='tfixed').find_all('div', class_='post classic')
        # print("ini postt>>>>>>>",parent_container)
        return parent_container

    def _get_last_page_number(self, soup):
        # Find div where class is exactly "pagination"
        parent_container = soup.find(
            lambda tag: tag.name == "div" and 
                    tag.get('class') == ["pagination"] and
                    (tag.get('style') is None or 'display: none' not in tag.get('style', ''))
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
    
    def _is_op(self, soup):
        return soup.find('a', class_='b-post__count js-show-post-link')
    
    # ------ Utility methods for saving the data ------

    def _save_post(self, data):
        # Create a unique query using both thread URL and post ID
        query = {
            "post_id": data.post_id
        }
        
        data_dict = fill_date(
            data.__dict__, data.post_id, self.mongodb_client)
        
        self.mongodb_client.upsert_document('darkweb', data_dict, query)
        # ------ Main methods to scrape the content ------

    def _scrape_post(self, post):
        try:
            poster = post.find('span', class_='largetext').text
            # print("ini poster", poster)
            post_id= post.find('div', class_='post_body scaleimages').get('id', '')
            if not post_id:
                # Fallback if no ID found
                post_id = f"{self.driver.current_url}_{number}"
        
            # if not poster:
            #     poster = postpost_id.find('span', {"class": "post-name"})
            div_post_head = post.find('div', class_='post_head')

            # Mencari <a> di dalam div_post_head dan mendapatkan teksnya
            data = div_post_head.find('a').text

            # Mengambil angka dari teks '#1'
            # Remove '#' and any commas, then convert to integer
            number = int(data.strip('#').replace(',', ''))
            
            is_op = (number == 1)
            
            pub_str = post.find('span', class_='post_date')
            time = pub_str if pub_str else None
            # print("ini tanggal", time.text)
            try:
                published_at = datetime.datetime.strptime(
                    time.text, '%b %d, %Y, %I:%M %p'
                )
            except:
                published_at = datetime.datetime.now()
                
                print("ini", published_at)
            
            post_content = post.find('div', class_="post_body scaleimages").text
            # print("ini post content", post_content)

            thread_topic = self._get_thread_topic(self._get_body_html())
            # print("ini topik", thread_topic)
            
            thread_section = self._get_thread_section(self._get_body_html())
            # print("ini section", thread_section)
            
            section_rapi = thread_section[:3]
            # print("ini section rapi", section_rapi)

            def clean_content(content):
                # Remove extra newlines
                content = re.sub(r'\n+', ' ', content)
                
                # Remove HTML tags
                content = re.sub(r'<[^>]+>', '', content)
                
                # Remove extra whitespaces
                content = re.sub(r'\s+', ' ', content).strip()
                
                return content
            
            
            return DarkPost(
                website=self.base_url,
                thread_url=self.driver.current_url,
                thread_topic=thread_topic.text,
                thread_section=section_rapi,
                poster=poster,
                published_at=time.text,
                content=clean_content(post_content),
                raw_content=str(post),
                post_media=None,
                post_id=post_id,  # Use the unique post ID instead of thread URL
                is_op=is_op
            )

        except Exception as e:
            logging.error(f"Error while scraping post: {e}")
            return None

    def scrape(self, url, idpost):
        # Initialize Tor connection once at the start
        self.driver.get(self.base_url)
        time.sleep(10)
        self.driver.get(url)
        time.sleep(15)

        try:
            soup = self._get_body_html()
            last_page = self._get_last_page_number(soup)
            logging.info(f"total page: {last_page}")
            total = 0

            for page in range(int(last_page)):
                page_url = url + f'?page={page + 1}'
                logging.info(f'Navigating to page: {page_url}')

                if page > 0:  # Only need to navigate if not on first page
                    self.driver.get(page_url)
                    time.sleep(15)

                posts = self._get_posts(self._get_body_html())
                logging.info(f" posts: {len(posts)}")

                for post in posts:
                    data = self._scrape_post(post)
                    if data:
                        logging.info(f"Saving post: {data.post_id}")
                        self._save_post(data)
                        logging.info(f"data: {data}")

                        total += 1
                        logging.info(f"Total posts: {total}")

            logging.info(f"Total posts scraped: {total}")
            return total

        finally:
            # Close Tor only once after all scraping is complete
            logging.info("Closing Tor browser")
            if self.driver:
                self.driver.quit()
                self.driver = None

    def run(self, url, idpost):
        print("Post")
        logging.info(f"Starting the scraper for {url}")
        time.sleep(5)
        total = self.scrape(url, idpost)
        logging.info(f"Scraping finished for {url}!")
        return total
