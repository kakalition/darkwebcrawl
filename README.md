# dawrkweb

Get onboard with our DarkWeb crawler! Dive into the shadows and pull the data you're looking for. Just follow the steps below to get started.


## 🚀 **Environment Setup**

- **Python Version:** 3.10
- **Supported Platforms:** Windows & Ubuntu.

1. 🌐 **Install the Tor Browser:** Essential for accessing `.onion` sites [link](https://www.torproject.org/download/).
2. 🦊 **Download Geckodriver:** Allows Selenium to interface with the Tor Browser [link](https://github.com/mozilla/geckodriver/releases).
3. 🛠 **Install Dependencies:**
```bash
$ pip install -r requirements.txt
```
4. ⚙️ **Update Configuration:** Modify `config.py` to suit your environment settings.
5. 🌐 **MongoDB Connection:** Create a `.env` file for MongoDB connection credentials.


## 🕸 **Running the Crawler**

- **For All Sites:**
```bash
$ python run.py
```

- **For Selected Sites:**

```bash
$ python run.py --sites <site-name1>,<site-name2>
```

## ➕ Adding URLs
Want to crawl specific forums or threads? Easy peasy! Just add the URLs in `config.py` under the respective site name:

```python
SITES = [
    {
        'name': 'breakingbad',
        'urls': [
            'http://bbzzz.../threads/the-undisputed-kings-of-drug-production...8103',
            # Add more URLs here...
        ]
    },
    # Add more sites as needed...
]
```

## 🌍 Adding New Sites
If you want to add more sites, just extend our BaseCrawler. Here's how:

1. Update the Config: Add the site's name and URLs to `config.py`.
2. Extend BaseCrawler: Your crawler module should implement the BaseCrawler from `src/base.py`. Take a look at the abstract class:

```python
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
```

**Happy Crawling! 🕷️**
