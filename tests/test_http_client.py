import pytest
from unittest.mock import MagicMock, patch
import requests
from verifier.http_client import HttpClient, HttpClientError


def make_config(url="https://localhost:5000", auth=None):
    """Создаёт фиктивный config для тестов."""
    config = MagicMock()
    config.emulator_url = url
    config.timeout = 30
    config.auth = auth
    return config


def make_client(url="https://localhost:5000"):
    return HttpClient(make_config(url))


# GET
def test_get_returns_response():
    """GET запрос возвращает ответ со статусом 200"""
    client = make_client()
    with patch.object(client.session, 'request') as mock_req:
        mock_req.return_value.status_code = 200
        response = client.get("/redfish/v1/")
        assert response.status_code == 200


def test_get_raises_on_connection_error():
    """GET бросает HttpClientError при ошибке соединения"""
    client = make_client()
    with patch.object(client.session, 'request') as mock_req:
        mock_req.side_effect = requests.exceptions.ConnectionError
        with pytest.raises(HttpClientError):
            client.get("/redfish/v1/")


def test_get_raises_on_timeout():
    """GET бросает HttpClientError при таймауте"""
    client = make_client()
    with patch.object(client.session, 'request') as mock_req:
        mock_req.side_effect = requests.exceptions.Timeout
        with pytest.raises(HttpClientError):
            client.get("/redfish/v1/")


# POST 
def test_post_returns_response():
    """POST запрос возвращает ответ со статусом 201"""
    client = make_client()
    with patch.object(client.session, 'request') as mock_req:
        mock_req.return_value.status_code = 201
        response = client.post("/redfish/v1/Volumes", {"Name": "vol1"})
        assert response.status_code == 201


# DELETE 
def test_delete_returns_response():
    """DELETE запрос возвращает ответ со статусом 204"""
    client = make_client()
    with patch.object(client.session, 'request') as mock_req:
        mock_req.return_value.status_code = 204
        response = client.delete("/redfish/v1/Volumes/1")
        assert response.status_code == 204


# PING 
def test_ping_returns_true_when_available():
    """ping() возвращает True если сервер отвечает 200"""
    client = make_client()
    with patch.object(client.session, 'request') as mock_req:
        mock_req.return_value.status_code = 200
        assert client.ping() is True


def test_ping_returns_false_when_unavailable():
    """ping() возвращает False если сервер недоступен"""
    client = make_client()
    with patch.object(client.session, 'request') as mock_req:
        mock_req.side_effect = requests.exceptions.ConnectionError
        assert client.ping() is False


def test_ping_returns_false_when_not_200():
    """ping() возвращает False если статус не 200"""
    client = make_client()
    with patch.object(client.session, 'request') as mock_req:
        mock_req.return_value.status_code = 403
        assert client.ping() is False


# GET MEMBERS
def test_get_members_returns_list():
    """get_members() возвращает список ответов для каждого члена коллекции"""
    client = make_client()
    with patch.object(client, 'get') as mock_get:
        collection = MagicMock()
        collection.json.return_value = {
            "Members": [
                {"@odata.id": "/redfish/v1/StorageSystems/1"},
                {"@odata.id": "/redfish/v1/StorageSystems/2"}
            ]
        }
        member_resp = MagicMock()
        mock_get.side_effect = [collection, member_resp, member_resp]
        results = client.get_members("/redfish/v1/StorageSystems")
        assert len(results) == 2


def test_get_members_returns_empty_on_error():
    """get_members() возвращает [] если сервер недоступен"""
    client = make_client()
    with patch.object(client, 'get') as mock_get:
        mock_get.side_effect = HttpClientError("нет соединения")
        results = client.get_members("/redfish/v1/StorageSystems")
        assert results == []


#URL 
def test_no_double_slash_in_url():
    """urljoin не создаёт двойных слэшей"""
    client = make_client("https://localhost:5000/")
    with patch.object(client.session, 'request') as mock_req:
        mock_req.return_value.status_code = 200
        client.get("/redfish/v1/")
        called_url = mock_req.call_args[0][1]
        assert "//" not in called_url.replace("https://", "")


# AUTH 
def test_auth_with_dataclass():
    """HttpClient принимает auth как dataclass объект"""
    auth = MagicMock()
    auth.username = "Administrator"
    auth.password = "Password"
    # убираем поведение dict чтобы isinstance(auth, dict) = False
    config = make_config(auth=auth)
    # Не должно бросать исключение
    client = HttpClient(config)
    assert client.session.auth == ("Administrator", "Password")


def test_auth_with_dict():
    """HttpClient принимает auth как словарь"""
    config = make_config(auth={"username": "admin", "password": "pass"})
    client = HttpClient(config)
    assert client.session.auth == ("admin", "pass")
