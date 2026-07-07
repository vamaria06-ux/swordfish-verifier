"""
Тесты для валидатора ответов Swordfish API.
"""

import pytest
from typing import Dict, Any, List

# Импортируем функции из валидатора
from verifier.validator import (
    validate_field_type,
    validate_resource,
    Validator,
    TYPE_NAMES
)


# ────────────────────────────────────────────────────────────────────────────
# Тесты для validate_field_type
# ────────────────────────────────────────────────────────────────────────────

class TestValidateFieldType:
    """Тесты проверки типов данных."""

    def test_string_field(self):
        """Поле типа str проходит проверку."""
        data = {"Name": "Root Service"}
        assert validate_field_type(data, "Name", str) is True

    def test_string_field_wrong_type(self):
        """Поле не является строкой — проверка не проходит."""
        data = {"Name": 123}
        assert validate_field_type(data, "Name", str) is False

    def test_integer_field(self):
        """Поле типа int проходит проверку."""
        data = {"Count": 10}
        assert validate_field_type(data, "Count", int) is True

    def test_integer_field_with_bool(self):
        """Поле с булевым значением НЕ проходит как int."""
        data = {"Count": True}
        assert validate_field_type(data, "Count", int) is False

    def test_missing_field(self):
        """Если поля нет — проверка не проходит."""
        data = {"Other": "value"}
        assert validate_field_type(data, "Name", str) is False

    def test_float_field(self):
        """Поле типа float проходит проверку (принимает и int, и float)."""
        data = {"Value": 3.14}
        assert validate_field_type(data, "Value", float) is True

    def test_float_field_with_int(self):
        """Поле с целым числом проходит как float."""
        data = {"Value": 42}
        assert validate_field_type(data, "Value", float) is True

    def test_list_field(self):
        """Поле типа list проходит проверку."""
        data = {"Members": [1, 2, 3]}
        assert validate_field_type(data, "Members", list) is True

    def test_dict_field(self):
        """Поле типа dict проходит проверку."""
        data = {"Metadata": {"key": "value"}}
        assert validate_field_type(data, "Metadata", dict) is True

    def test_bool_field(self):
        """Поле типа bool проходит проверку."""
        data = {"IsEnabled": True}
        assert validate_field_type(data, "IsEnabled", bool) is True


# ────────────────────────────────────────────────────────────────────────────
# Тесты для validate_resource
# ────────────────────────────────────────────────────────────────────────────

class TestValidateResource:
    """Тесты проверки ресурсов по правилам."""

    def test_all_fields_pass(self):
        """Все обязательные поля есть и имеют правильный тип."""
        data = {
            "Id": "RootService",
            "Name": "Root Service",
            "RedfishVersion": "1.18.0"
        }
        required_fields = {
            "Id": {"type": str, "spec": "Таблица 9"},
            "Name": {"type": str, "spec": "Таблица 9"},
            "RedfishVersion": {"type": str, "spec": "Раздел 8.1"}
        }

        results = validate_resource(data, required_fields)

        # Должно быть 3 результата, все PASS
        assert len(results) == 3
        assert all(r["status"] == "PASS" for r in results)

    def test_missing_required_field(self):
        """Отсутствует обязательное поле → FAIL."""
        data = {
            "Name": "Root Service"
            # Id отсутствует
        }
        required_fields = {
            "Id": {"type": str, "spec": "Таблица 9"},
            "Name": {"type": str, "spec": "Таблица 9"}
        }

        results = validate_resource(data, required_fields)

        # Ищем результат для поля Id — должен быть FAIL
        id_result = next(r for r in results if "Id" in r["check"])
        assert id_result["status"] == "FAIL"
        assert "отсутствует" in id_result["detail"]

    def test_wrong_type(self):
        """Поле есть, но неправильный тип → FAIL."""
        data = {
            "Id": 12345  # должно быть str
        }
        required_fields = {
            "Id": {"type": str, "spec": "Таблица 9"}
        }

        results = validate_resource(data, required_fields)

        assert len(results) == 1
        assert results[0]["status"] == "FAIL"
        assert "неверный тип" in results[0]["detail"]

    def test_empty_required_fields(self):
        """Нет обязательных полей — возвращаем пустой список."""
        data = {"Some": "data"}
        required_fields = {}

        results = validate_resource(data, required_fields)

        assert results == []


# ────────────────────────────────────────────────────────────────────────────
# Тесты для Validator
# ────────────────────────────────────────────────────────────────────────────

class TestValidator:
    """Тесты класса Validator."""

    def test_validate_success(self):
        """Полная проверка успешного ответа."""
        # Создаём мок-ответ
        class MockResponse:
            def __init__(self):
                self.status_code = 200
                self._json = {
                    "Id": "RootService",
                    "Name": "Root Service",
                    "RedfishVersion": "1.18.0"
                }

            def json(self):
                return self._json

        response = MockResponse()
        rule = {
            "endpoint": "/redfish/v1/",
            "expected_status": 200,
            "spec_section": "Раздел 8.3",
            "spec_url": "https://example.com",
            "required_fields": {
                "Id": {"type": str, "spec": "Таблица 9"},
                "Name": {"type": str, "spec": "Таблица 9"}
            }
        }

        validator = Validator()
        results = validator.validate(response, rule, "ServiceRoot")

        # Проверяем, что все проверки пройдены
        assert len(results) >= 4  # статус, JSON + 2 поля
        assert all(r["status"] == "PASS" for r in results)

    def test_validate_connection_error(self):
        """Ошибка подключения → FAIL."""
        validator = Validator()
        rule = {"endpoint": "/redfish/v1/"}
        results = validator.validate(None, rule, "ServiceRoot")

        assert len(results) == 1
        assert results[0]["status"] == "FAIL"
        assert "недоступен" in results[0]["detail"]

    def test_validate_wrong_status(self):
        """Неправильный HTTP статус → FAIL."""
        class MockResponse:
            def __init__(self):
                self.status_code = 404

            def json(self):
                return {}

        response = MockResponse()
        rule = {
            "endpoint": "/redfish/v1/",
            "expected_status": 200,
            "required_fields": {}
        }

        validator = Validator()
        results = validator.validate(response, rule, "ServiceRoot")

        # Ищем проверку статуса — должна быть FAIL
        status_result = next(r for r in results if "HTTP статус" in r["check"])
        assert status_result["status"] == "FAIL"

    def test_validate_invalid_json(self):
        """Невалидный JSON → FAIL."""
        class MockResponse:
            def __init__(self):
                self.status_code = 200

            def json(self):
                raise ValueError("Invalid JSON")

        response = MockResponse()
        rule = {
            "endpoint": "/redfish/v1/",
            "expected_status": 200,
            "required_fields": {}
        }

        validator = Validator()
        results = validator.validate(response, rule, "ServiceRoot")

        # Ищем проверку JSON — должна быть FAIL
        json_result = next(r for r in results if "JSON" in r["check"])
        assert json_result["status"] == "FAIL"


# ────────────────────────────────────────────────────────────────────────────
# Тесты для TYPE_NAMES (проверяем, что словарь заполнен правильно)
# ────────────────────────────────────────────────────────────────────────────

class TestTypeNames:
    """Тесты словаря с именами типов."""

    def test_all_types_present(self):
        """Все типы из словаря определены."""
        expected_types = [str, int, float, list, dict, bool]
        assert all(t in TYPE_NAMES for t in expected_types)

    def test_type_names_are_strings(self):
        """Все имена типов — строки."""
        assert all(isinstance(v, str) for v in TYPE_NAMES.values())
        


# ────────────────────────────────────────────────────────────────────────────
# Тесты для статуса NOT_SUPPORTED
# ────────────────────────────────────────────────────────────────────────────

class TestNotSupportedStatus:
    """
    NOT_SUPPORTED должен использоваться, когда верификатор не может выполнить
    проверку (нет правила для ресурса или тип поля не распознан по схеме),
    а не молча становиться PASS или ошибочным FAIL.
    """

    def test_validate_resource_without_rule_is_not_supported(self):
        """Если для ресурса вообще нет правила -- статус NOT_SUPPORTED."""
        validator = Validator()
        results = validator.validate(response=None, rule={}, resource_name="UnknownResource")

        assert len(results) == 1
        assert results[0]["status"] == "NOT_SUPPORTED"
        assert results[0]["resource"] == "UnknownResource"

    def test_validate_resource_with_none_rule_is_not_supported(self):
        """rule=None обрабатывается так же, как отсутствие правила."""
        validator = Validator()
        results = validator.validate(response=None, rule=None, resource_name="UnknownResource")

        assert len(results) == 1
        assert results[0]["status"] == "NOT_SUPPORTED"

    def test_field_with_unresolvable_type_is_not_supported(self):
        """Тип поля не распознан верификатором -> NOT_SUPPORTED, а не FAIL."""
        data = {"WeirdField": "some value"}
        required_fields = {
            "WeirdField": {"type": "totally-unknown-type", "spec": "Раздел X"}
        }

        results = validate_resource(data, required_fields)

        assert len(results) == 1
        assert results[0]["status"] == "NOT_SUPPORTED"

    def test_field_without_type_is_not_supported(self):
        """Если тип поля вообще не задан в схеме -> NOT_SUPPORTED."""
        data = {"WeirdField": "some value"}
        required_fields = {
            "WeirdField": {"spec": "Раздел X"}
        }

        results = validate_resource(data, required_fields)

        assert len(results) == 1
        assert results[0]["status"] == "NOT_SUPPORTED"

    def test_missing_field_is_still_fail_not_not_supported(self):
        """Отсутствие поля -- это FAIL, а не NOT_SUPPORTED, даже без типа."""
        data = {}
        required_fields = {
            "MissingField": {"type": "totally-unknown-type"}
        }

        results = validate_resource(data, required_fields)

        assert len(results) == 1
        assert results[0]["status"] == "FAIL"


# ────────────────────────────────────────────────────────────────────────────
# Тесты для проверки enum-значений
# ────────────────────────────────────────────────────────────────────────────

class TestEnumValidation:
    """Тесты валидации значений по списку допустимых (enum)."""

    def test_enum_value_allowed(self):
        data = {"Status": "Enabled"}
        required_fields = {
            "Status": {"type": str, "enum": ["Enabled", "Disabled"]}
        }

        results = validate_resource(data, required_fields)

        assert len(results) == 1
        assert results[0]["status"] == "PASS"

    def test_enum_value_not_allowed(self):
        data = {"Status": "Broken"}
        required_fields = {
            "Status": {"type": str, "enum": ["Enabled", "Disabled"]}
        }

        results = validate_resource(data, required_fields)

        assert len(results) == 1
        assert results[0]["status"] == "FAIL"
        assert "Broken" in results[0]["detail"]

    def test_no_enum_defined_just_checks_type(self):
        """Если enum не задан в схеме -- проверяется только тип."""
        data = {"Status": "AnyString"}
        required_fields = {
            "Status": {"type": str}
        }

        results = validate_resource(data, required_fields)

        assert len(results) == 1
        assert results[0]["status"] == "PASS"
