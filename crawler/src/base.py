from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

from config import BINARY_PATH, GECKO_DRIVER_PATH, PROFILE_PATH
from selenium_config import SeleniumConfig


@dataclass
class DarkPost:
    website: str
    thread_url: str
    thread_topic: str
    thread_section: List[str]
    poster: str
    published_at: str
    content: str
    raw_content: str
    post_media: List[str]
    post_id: str
    is_op: bool
    


@dataclass
class DarkProfile:
    website: str
    username: str
    user_title: str
    date_joined: str
    last_seen: str
    messages: str
    reaction_score: str
    points:str
    followers: str
    following: str
    avatar: str
    additional: dict


class BaseCrawler(ABC):
    def __init__(self):
        self.driver = self.init_driver()

    @abstractmethod
    def init_driver(self):
        driver_config = SeleniumConfig(GECKO_DRIVER_PATH, BINARY_PATH, PROFILE_PATH)
        return driver_config.create_firefox_driver()

    @abstractmethod
    def scrape(self):
        pass

    @abstractmethod
    def run(self):
        pass
