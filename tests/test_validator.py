"""
Тесты для verifier/validator.py

Проверяем логику Тани: наличие полей, типы, enum значения.
Проверяем интеграцию с форматом правил из parser.py.
"""

import pytest
from unittest.mock import MagicMock
from verifier.validator import (
    Validator,
    validate_resource,
    validate_field_type,
    validate_enum,
)

SPEC_URL = "https://snia.org/swordfish"

RULE = {
    "endpoint":        "/redfish/v1/",
    "method":          "GET",
    "expected_status": 200,
    "spec_section":    "Раздел 8.3",
    "spec_url":        SPEC_URL,
    "dynamic":         False,
    "required_fields": {
        "@odata.type": {"type": str,  "description": "Тип ресурса", "spec": "Раздел 7.2"},
        "@odata.id":   {"type": str,  "description": "Идентификатор", "spec": "Раздел 7.2"},
        "Id":          {"type": str,  "description": "Строковый id", "spec": "Таблица 9"},
        "Name":        {"type": str,  "description": "Имя", "spec": "Таблица 9"},
    }
}


def make_response(status_code, body):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = body
    return r


#  Validator.validate()

def test_pass_when_all_correct():
    """Все поля верные — нет FAIL"""
    validator = Validator()
    response = make_response(200, {
        "@odata.type": "#ServiceRoot.v1_0_0.ServiceRoot",
        "@odata.id":   "/redfish/v1/",
        "Id":          "RootService",
        "Name":        "Root Service"
    })
    results = validator.validate(response, RULE, "ServiceRoot")
    fails = [r for r in results if r["status"] == "FAIL"]
    assert len(fails) == 0


def test_fail_when_status_wrong():
    """Статус 404 → FAIL на HTTP статус"""
    validator = Validator()
    response = make_response(404, {})
    results = validator.validate(response, RULE, "ServiceRoot")
    status_check = next(r for r in results if r["check"] == "HTTP статус код")
    assert status_check["status"] == "FAIL"
    assert "404" in status_check["detail"]
    assert "200" in status_check["detail"]


def test_fail_when_field_missing():
    """Нет полей Id и Name → 2 FAIL"""
    validator = Validator()
    response = make_response(200, {
        "@odata.type": "#ServiceRoot.v1_0_0.ServiceRoot",
        "@odata.id":   "/redfish/v1/",
    })
    results = validator.validate(response, RULE, "ServiceRoot")
    fails = [r for r in results if r["status"] == "FAIL"]
    assert len(fails) == 2


def test_fail_when_wrong_type():
    """Id=число вместо строки → FAIL на тип"""
    validator = Validator()
    response = make_response(200, {
        "@odata.type": "#ServiceRoot.v1_0_0.ServiceRoot",
        "@odata.id":   "/redfish/v1/",
        "Id":          123,
        "Name":        "Root Service"
    })
    results = validator.validate(response, RULE, "ServiceRoot")
    type_fails = [r for r in results if r["status"] == "FAIL"]
    assert len(type_fails) == 1
    assert "строка" in type_fails[0]["detail"]
    assert "целое число" in type_fails[0]["detail"]


def test_fail_when_emulator_unavailable():
    """response=None → FAIL на доступность"""
    validator = Validator()
    results = validator.validate(None, RULE, "ServiceRoot")
    assert len(results) == 1
    assert results[0]["status"] == "FAIL"
    assert "недоступен" in results[0]["detail"]


def test_result_has_spec_reference():
    """Каждый результат содержит spec_section и spec_url"""
    validator = Validator()
    response = make_response(200, {
        "@odata.type": "#ServiceRoot.v1_0_0.ServiceRoot",
        "@odata.id":   "/redfish/v1/",
        "Id":          "Root",
        "Name":        "Root"
    })
    results = validator.validate(response, RULE, "ServiceRoot")
    for r in results:
        assert "spec_section" in r
        assert "spec_url" in r


def test_result_has_expected_and_actual():
    """FAIL результат содержит expected и actual"""
    validator = Validator()
    response = make_response(404, {})
    results = validator.validate(response, RULE, "ServiceRoot")
    status_fail = next(r for r in results if r["check"] == "HTTP статус код")
    assert status_fail["expected"] == "200"
    assert status_fail["actual"] == "404"


# validate_field_type (логика Тани)

def test_bool_not_accepted_as_int():
    """True/False не считается целым числом — важная деталь от Тани"""
    assert validate_field_type({"field": True}, "field", int) is False
    assert validate_field_type({"field": False}, "field", int) is False
    assert validate_field_type({"field": 42}, "field", int) is True


def test_int_accepted_as_float():
    """Целое число принимается там где ожидается float"""
    assert validate_field_type({"field": 42}, "field", float) is True
    assert validate_field_type({"field": 3.14}, "field", float) is True
    assert validate_field_type({"field": True}, "field", float) is False


# validate_enum (логика Тани)

def test_enum_pass_for_valid_value():
    """Значение из списка → True"""
    data = {"VolumeType": "Mirrored"}
    assert validate_enum(data, "VolumeType",
                         ["RawDevice", "NonRedundant", "Mirrored"]) is True


def test_enum_fail_for_invalid_value():
    """Значение не из списка → False"""
    data = {"VolumeType": "Unknown"}
    assert validate_enum(data, "VolumeType",
                         ["RawDevice", "NonRedundant", "Mirrored"]) is False


# validate_resource (логика Тани)

def test_validate_resource_required_missing():
    """Обязательное поле отсутствует → FAIL"""
    results = validate_resource(
        data={},
        rules=[{"field": "Id", "type": str, "required": True}]
    )
    assert results[0]["status"] == "FAIL"


def test_validate_resource_optional_missing():
    """Необязательное поле отсутствует → NOT_SUPPORTED"""
    results = validate_resource(
        data={},
        rules=[{"field": "Description", "type": str, "required": False}]
    )
    assert results[0]["status"] == "NOT_SUPPORTED"


def test_validate_resource_all_pass():
    """Все поля верные → все PASS"""
    results = validate_resource(
        data={"Id": "1", "Name": "Test"},
        rules=[
            {"field": "Id",   "type": str, "required": True},
            {"field": "Name", "type": str, "required": True},
        ]
    )
    assert all(r["status"] == "PASS" for r in results)
