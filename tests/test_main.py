"""
Юнит-тесты для main.py: получение id систем (get_system_urls) и
обработка динамических ресурсов в run_checks, если система недоступна.
"""

from unittest.mock import MagicMock

from main import get_system_urls, run_checks


def _response(status_code, body=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body or {}
    return resp


def test_get_system_urls_uses_storage_systems_when_available():
    """Если StorageSystems отдаёт Members - используем их, Systems не спрашиваем."""
    def get(endpoint):
        if endpoint == "/redfish/v1/StorageSystems":
            return _response(200, {"Members": [{"@odata.id": "/redfish/v1/StorageSystems/1"}]})
        raise AssertionError(f"неожиданный запрос к {endpoint}")

    client = MagicMock()
    client.get.side_effect = get

    assert get_system_urls(client) == ["/redfish/v1/StorageSystems/1"]


def test_get_system_urls_falls_back_to_systems_when_storage_systems_unavailable():
    """StorageSystems недоступен (404) -> используем /redfish/v1/Systems."""
    def get(endpoint):
        if endpoint == "/redfish/v1/StorageSystems":
            return _response(404)
        if endpoint == "/redfish/v1/Systems":
            return _response(200, {"Members": [{"@odata.id": "/redfish/v1/Systems/1"}]})
        raise AssertionError(f"неожиданный запрос к {endpoint}")

    client = MagicMock()
    client.get.side_effect = get

    assert get_system_urls(client) == ["/redfish/v1/Systems/1"]


def test_get_system_urls_falls_back_when_storage_systems_has_no_members():
    """StorageSystems отдаёт 200, но без Members -> тоже нужен fallback на Systems."""
    def get(endpoint):
        if endpoint == "/redfish/v1/StorageSystems":
            return _response(200, {"Members": []})
        if endpoint == "/redfish/v1/Systems":
            return _response(200, {"Members": [{"@odata.id": "/redfish/v1/Systems/1"}]})
        raise AssertionError(f"неожиданный запрос к {endpoint}")

    client = MagicMock()
    client.get.side_effect = get

    assert get_system_urls(client) == ["/redfish/v1/Systems/1"]


def test_get_system_urls_returns_empty_when_both_unavailable():
    client = MagicMock()
    client.get.return_value = None

    assert get_system_urls(client) == []


def _dynamic_rules():
    return {
        "StoragePools": {"endpoint": "{system_url}/StoragePools", "dynamic": True},
        "Volumes": {"endpoint": "{system_url}/Volumes", "dynamic": True},
        "Drives": {"endpoint": "{system_url}/Drives", "dynamic": True},
    }


def test_run_checks_reports_skip_for_every_dynamic_resource_without_system(capsys):
    """
    Регрессионный тест: раньше сообщение "<ресурс> - пропущен" печаталось
    только для ПЕРВОГО динамического ресурса, а остальные (StoragePools/
    Volumes/Drives) молча пропадали из вывода, если система недоступна.
    """
    client = MagicMock()
    client.get.return_value = None  # StorageSystems и Systems оба недоступны

    validator = MagicMock()
    results = run_checks(client, validator, _dynamic_rules())

    captured = capsys.readouterr()
    assert results == []
    for name in ("StoragePools", "Volumes", "Drives"):
        assert f"{name} — пропущен" in captured.out


def test_run_checks_checks_every_dynamic_resource_when_system_available():
    """Если система найдена - проверяются ВСЕ динамические ресурсы, а не только первый."""
    def get(endpoint):
        if endpoint == "/redfish/v1/StorageSystems":
            return _response(200, {"Members": [{"@odata.id": "/redfish/v1/StorageSystems/1"}]})
        return _response(200, {})

    client = MagicMock()
    client.get.side_effect = get

    validator = MagicMock()
    validator.validate.return_value = [{"status": "PASS"}]

    run_checks(client, validator, _dynamic_rules())

    checked_resources = {
        call.args[2].split(" (")[0] for call in validator.validate.call_args_list
    }
    assert checked_resources == {"StoragePools", "Volumes", "Drives"}
