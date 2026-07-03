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
            