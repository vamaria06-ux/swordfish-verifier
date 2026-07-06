"""
HTTP-клиент для взаимодействия с Swordfish API эмулятором.

Поддерживает методы GET, POST, DELETE.
Аутентификация: Basic Auth.
SSL: проверка отключена (эмулятор использует самоподписанный сертификат).

Вместо возврата None при ошибках — бросает HttpClientError.
Это позволяет вызывающему коду явно обрабатывать ошибки
через try/except вместо постоянных проверок if response is None.
"""

import requests
import urllib3
import logging
from urllib.parse import urljoin

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)


class HttpClientError(Exception):
    """
    Исключение HTTP-клиента.
    Бросается при ошибках соединения, таймауте или недоступности сервера.
    """


class HttpClient:
    """
    HTTP-клиент для Swordfish API.

    Принимает объект Config и выполняет запросы к эмулятору.
    Все методы бросают HttpClientError при проблемах с сетью.
    """

    def __init__(self, config):
        """
        Инициализация клиента.

        :param config: объект Config с полями emulator_url, timeout, auth
        """
        self.base_url = config.emulator_url.rstrip("/")
        self.timeout = config.timeout
        self.session = requests.Session()

        # Отключаем проверку SSL — эмулятор использует самоподписанный сертификат
        self.session.verify = False

        # Настраиваем Basic Auth если указан в конфиге
        if config.auth:
            # Поддерживаем оба формата: dict и dataclass
            if isinstance(config.auth, dict):
                username = config.auth.get("username")
                password = config.auth.get("password")
            else:
                username = config.auth.username
                password = config.auth.password

            if username and password:
                self.session.auth = (username, password)

    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        Общий метод для всех HTTP запросов.
        Используется внутри get(), post(), delete().

        :param method: HTTP метод — "GET", "POST", "DELETE"
        :param endpoint: путь к ресурсу, например "/redfish/v1/"
        :param kwargs: дополнительные параметры для requests (json, headers и т.д.)
        :raises HttpClientError: при ошибке соединения или таймауте
        :return: объект Response
        """
        # urljoin корректно склеивает URL без двойных слэшей
        # urljoin("https://localhost:5000", "/redfish/v1/") = "https://localhost:5000/redfish/v1/"
        url = urljoin(self.base_url + "/", endpoint.lstrip("/"))
        logger.info(f"{method} {url}")

        try:
            response = self.session.request(
                method,
                url,
                timeout=self.timeout,
                **kwargs
            )
            return response

        except requests.exceptions.ConnectionError:
            logger.error(f"Нет соединения: {url}")
            raise HttpClientError(f"Нет соединения с сервером: {url}")

        except requests.exceptions.Timeout:
            logger.error(f"Таймаут: {url}")
            raise HttpClientError(f"Таймаут при запросе к: {url}")

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка запроса {url}: {e}")
            raise HttpClientError(f"Ошибка запроса: {e}")

    def get(self, endpoint: str) -> requests.Response:
        """
        GET запрос к эмулятору.

        :param endpoint: путь к ресурсу, например "/redfish/v1/StorageSystems"
        :raises HttpClientError: при ошибке соединения или таймауте
        :return: объект Response (status_code, json() и т.д.)
        """
        return self._request("GET", endpoint)

    def post(self, endpoint: str, body: dict) -> requests.Response:
        """
        POST запрос к эмулятору (создание ресурса).

        :param endpoint: путь к ресурсу
        :param body: тело запроса в виде словаря (будет сериализован в JSON)
        :raises HttpClientError: при ошибке соединения или таймауте
        :return: объект Response
        """
        return self._request("POST", endpoint, json=body)

    def delete(self, endpoint: str) -> requests.Response:
        """
        DELETE запрос к эмулятору (удаление ресурса).

        :param endpoint: путь к ресурсу
        :raises HttpClientError: при ошибке соединения или таймауте
        :return: объект Response
        """
        return self._request("DELETE", endpoint)

    def get_members(self, endpoint: str) -> list:
        """
        Получает список всех членов коллекции.
        Сначала запрашивает коллекцию, затем каждый элемент из Members.

        :param endpoint: путь к коллекции, например "/redfish/v1/StorageSystems"
        :return: список объектов Response для каждого члена коллекции
        """
        try:
            response = self.get(endpoint)
        except HttpClientError:
            return []

        try:
            members = response.json().get("Members", [])
        except Exception:
            return []

        results = []
        for member in members:
            member_url = member.get("@odata.id")
            if member_url:
                try:
                    r = self.get(member_url)
                    results.append(r)
                except HttpClientError:
                    logger.warning(f"Не удалось получить член коллекции: {member_url}")

        return results

    def ping(self) -> bool:
        """
        Проверяет доступность сервера.
        Делает GET запрос на /redfish/v1/ и проверяет статус 200.

        :return: True если сервер доступен и отвечает 200, иначе False
        """
        try:
            response = self.get("/redfish/v1/")
            return response.status_code == 200
        except HttpClientError:
            return False
