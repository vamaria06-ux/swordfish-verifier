"""
Дополнительные интеграционные тесты для mock-сервера: проверяем
динамические ресурсы StoragePools/Volumes/Drives под
/redfish/v1/StorageSystems/1/... (см. mock_server/broken_server.py).

Раньше mock-сервер вообще не реализовывал эти ресурсы, поэтому
tests/test_mock_integration.py явно их пропускает (см. комментарий
"пропускаем StoragePools/Volumes/Drives - нужен id системы"). Эти тесты
покрывают именно то, что раньше не проверялось.
"""

import threading
import time

import pytest
from unittest.mock import MagicMock

from verifier.http_client import HttpClient
from verifier.parser import Parser
from verifier.validator import Validator
from main import get_system_urls

MOCK_PORT = 5002


def make_config(url):
    config = MagicMock()
    config.emulator_url = url
    config.timeout = 5
    config.auth = None
    return config


@pytest.fixture(scope="module")
def mock_server():
    """Запускает broken_server в отдельном потоке на время тестов."""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from mock_server.broken_server import app

    thread = threading.Thread(
        target=lambda: app.run(
            host="127.0.0.1", port=MOCK_PORT,
            debug=False, use_reloader=False
        )
    )
    thread.daemon = True
    thread.start()
    time.sleep(1)
    yield


@pytest.fixture
def client():
    return HttpClient(make_config(f"http://localhost:{MOCK_PORT}"))


def test_get_system_urls_against_mock_server_falls_back_to_systems(mock_server, client):
    """
    StorageSystems у mock-сервера намеренно отдаёт 404 -> get_system_urls
    должен подхватить id системы из /redfish/v1/Systems.
    """
    assert get_system_urls(client) == ["/redfish/v1/StorageSystems/1"]


def test_mock_storage_pools_count_type_mismatch(mock_server, client):
    """StoragePools: Members@odata.count строка вместо числа -> FAIL."""
    parser = Parser()
    validator = Validator()
    rules = parser.load_rules()

    response = client.get("/redfish/v1/StorageSystems/1/StoragePools")
    results = validator.validate(response, rules["StoragePools"], "StoragePools")

    count_check = next(r for r in results if r["check"] == "Поле: Members@odata.count")
    assert count_check["status"] == "FAIL"


def test_mock_volumes_missing_members(mock_server, client):
    """Volumes: намеренно отсутствуют Members и Members@odata.count -> FAIL."""
    parser = Parser()
    validator = Validator()
    rules = parser.load_rules()

    response = client.get("/redfish/v1/StorageSystems/1/Volumes")
    results = validator.validate(response, rules["Volumes"], "Volumes")

    fails = {r["check"] for r in results if r["status"] == "FAIL"}
    assert "Обязательное поле: Members" in fails
    assert "Обязательное поле: Members@odata.count" in fails


def test_mock_drives_endpoint_missing(mock_server, client):
    """Drives: эндпоинт вообще не реализован -> 404 -> FAIL по статусу."""
    parser = Parser()
    validator = Validator()
    rules = parser.load_rules()

    response = client.get("/redfish/v1/StorageSystems/1/Drives")
    results = validator.validate(response, rules["Drives"], "Drives")

    status_check = next(r for r in results if r["check"] == "HTTP статус код")
    assert status_check["status"] == "FAIL"


def test_all_six_core_resources_produce_results_end_to_end(mock_server, client):
    """
    Сквозная проверка: раньше проверялось только 3 статических ресурса
    (ServiceRoot/Systems/StorageSystems), а 3 динамических либо не
    реализовывались mock-сервером, либо молча пропадали из вывода
    (см. main.py: run_checks). Теперь для всех 6 базовых ресурсов должен
    быть хотя бы один результат проверки.
    """
    parser = Parser()
    validator = Validator()
    rules = parser.load_rules()

    system_urls = get_system_urls(client)
    assert system_urls, "get_system_urls не должен возвращать пустой список"

    results_by_resource = {}
    for resource_name, rule in rules.items():
        if rule.get("dynamic"):
            for system_url in system_urls:
                endpoint = rule["endpoint"].replace("{system_url}", system_url)
                actual_rule = dict(rule)
                actual_rule["endpoint"] = endpoint
                response = client.get(endpoint)
                results_by_resource.setdefault(resource_name, []).extend(
                    validator.validate(response, actual_rule, resource_name)
                )
        else:
            response = client.get(rule["endpoint"])
            results_by_resource[resource_name] = validator.validate(
                response, rule, resource_name
            )

    for name in ("ServiceRoot", "Systems", "StorageSystems",
                 "StoragePools", "Volumes", "Drives"):
        assert results_by_resource.get(name), f"{name} должен дать хотя бы один результат"
