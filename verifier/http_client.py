import requests
import urllib3
import logging

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

class HttpClient:

    def __init__(self, config):
        self.base_url = config.emulator_url
        self.timeout = config.timeout
        self.session = requests.Session()
        self.session.verify = False
        if config.auth:
            self.session.auth = (
                config.auth["username"],
                config.auth["password"]
            )
    def get(self, endpoint):
        url = self.base_url + endpoint
        logger.info(f"GET {url}")
        try:
            response = self.session.get(url, timeout=self.timeout)
            return response
        except requests.exceptions.ConnectionError:
            logger.error(f"Нет соединения: {url}")
            return None
        except requests.exceptions.Timeout:
            logger.error(f"Таймаут: {url}")
            return None

    def post(self, endpoint, body):
        url = self.base_url + endpoint
        logger.info(f"POST {url}")
        try:
            response = self.session.post(
                url,
                json=body,
                timeout=self.timeout
            )
            return response
        except requests.exceptions.ConnectionError:
            logger.error(f"Нет соединения: {url}")
            return None
        except requests.exceptions.Timeout:
            logger.error(f"Таймаут: {url}")
            return None

    def delete(self, endpoint):
        url = self.base_url + endpoint
        logger.info(f"DELETE {url}")
        try:
            response = self.session.delete(url, timeout=self.timeout)
            return response
        except requests.exceptions.ConnectionError:
            logger.error(f"Нет соединения: {url}")
            return None
        except requests.exceptions.Timeout:
            logger.error(f"Таймаут: {url}")
            return None 