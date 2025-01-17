from selenium import webdriver
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile


class SeleniumConfig:
    def __init__(self, geckodriver_path, binary_path, profile_path):
        self.geckodriver_path = geckodriver_path
        self.binary_path = binary_path
        self.profile_path = profile_path
        self.options = self._set_options()

    def _set_options(self):
        options = webdriver.FirefoxOptions()
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--incognito")
        options.add_argument("--disable-infobars")
        options.add_argument("--no-sandbox")
        options.add_argument("window-size=1920,1080")
        options.add_argument("--start-maximized")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument("disable-blink-features=AutomationControlled")
        options.add_argument(
            "user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 12_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/7.0.4 Mobile/16B91 Safari/605.1.15"
        )
        return options

    def create_firefox_driver(self):
        binary = FirefoxBinary(self.binary_path)
        profile = FirefoxProfile(self.profile_path)
        return webdriver.Firefox(
            profile, binary, executable_path=self.geckodriver_path, options=self.options
        )

    def __del__(self):
        try:
            self.driver.quit()
        except AttributeError:
            pass
