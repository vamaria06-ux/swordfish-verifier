"""
Интеграционные тесты с mock-сервером.
Проверяем что верификатор правильно находит ошибки в неправильных ответах.
"""

import threading
import time
import pytest
from unittest.mock import MagicMock
from verifier.http_client import HttpClient
from verifier.parser import Parser
from verifier.validator import Validator


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
            host="127.0.0.1", port=5001,
            debug=False, use_reloader=False
        )
    )
    thread.daemon = True
    thread.start()
    time.sleep(1)
    yield


def test_mock_service_root_has_failures(mock_server):
    """ServiceRoot — нет обязательных полей → FAIL"""
    config = make_config("http://localhost:5001")
    client = HttpClient(config)
    parser = Parser()
    validator = Validator()

    rules = parser.load_rules()
    response = client.get("/redfish/v1/")
    results = validator.validate(response, rules["ServiceRoot"], "ServiceRoot")

    fails = [r for r in results if r["status"] == "FAIL"]
    assert len(fails) > 0, "Верификатор должен найти ошибки в ServiceRoot"


def test_mock_storage_systems_returns_404(mock_server):
    """StorageSystems → 404 → FAIL на статус код"""
    config = make_config("http://localhost:5001")
    client = HttpClient(config)
    parser = Parser()
    validator = Validator()

    rules = parser.load_rules()
    response = client.get("/redfish/v1/StorageSystems")
    results = validator.validate(
        response, rules["StorageSystems"], "StorageSystems"
    )

    status_check = next(r for r in results if r["check"] == "HTTP статус код")
    assert status_check["status"] == "FAIL"


def test_mock_systems_passes(mock_server):
    """Systems — правильный ответ → все PASS"""
    config = make_config("http://localhost:5001")
    client = HttpClient(config)
    parser = Parser()
    validator = Validator()

    rules = parser.load_rules()
    response = client.get("/redfish/v1/Systems")
    results = validator.validate(response, rules["Systems"], "Systems")

    fails = [r for r in results if r["status"] == "FAIL"]
    assert len(fails) == 0, "Systems должен пройти без ошибок"


def test_verifier_distinguishes_pass_and_fail(mock_server):
    """Верификатор различает правильные и неправильные ответы — только статические ресурсы"""
    config = make_config("http://localhost:5001")
    client = HttpClient(config)
    parser = Parser()
    validator = Validator()

    rules = parser.load_rules()
    all_results = []

    # проверяем только статические ресурсы (без динамических)
    for resource_name, rule in rules.items():
        if rule.get("dynamic"):
            continue  # пропускаем StoragePools/Volumes/Drives — нужен id системы
        response = client.get(rule["endpoint"])
        results = validator.validate(response, rule, resource_name)
        all_results.extend(results)

    passes = [r for r in all_results if r["status"] == "PASS"]
    fails = [r for r in all_results if r["status"] == "FAIL"]

    assert len(passes) > 0, "Должны быть хоть какие-то PASS"
    assert len(fails) > 0, "Должны быть хоть какие-то FAIL"
