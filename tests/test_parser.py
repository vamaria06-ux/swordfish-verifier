"""
Тесты для модуля parser.py
Проверяем что правила загружаются правильно для всех 6 ресурсов.
"""

from verifier.parser import Parser


def test_rules_loaded():
    """Правила загружаются и не пустые"""
    parser = Parser()
    rules = parser.load_rules()
    assert len(rules) > 0


def test_all_six_resources_present():
    """Все 6 обязательных ресурсов из ТЗ присутствуют"""
    parser = Parser()
    rules = parser.load_rules()
    required = [
        "ServiceRoot",
        "Systems",
        "StorageSystems",
        "StoragePools",
        "Volumes",
        "Drives"
    ]
    for resource in required:
        assert resource in rules, f"Ресурс {resource} отсутствует"


def test_service_root_has_correct_endpoint():
    """ServiceRoot имеет правильный эндпоинт"""
    parser = Parser()
    rules = parser.load_rules()
    assert rules["ServiceRoot"]["endpoint"] == "/redfish/v1/"
    assert rules["ServiceRoot"]["expected_status"] == 200
    assert rules["ServiceRoot"]["dynamic"] == False


def test_dynamic_resources_marked_correctly():
    """StoragePools, Volumes, Drives помечены как динамические"""
    parser = Parser()
    rules = parser.load_rules()
    for resource in ["StoragePools", "Volumes", "Drives"]:
        assert rules[resource]["dynamic"] == True, \
            f"{resource} должен быть dynamic=True"
        assert "{system_url}" in rules[resource]["endpoint"], \
            f"{resource} должен содержать {{system_url}} в эндпоинте"


def test_static_resources_marked_correctly():
    """ServiceRoot, Systems, StorageSystems помечены как статические"""
    parser = Parser()
    rules = parser.load_rules()
    for resource in ["ServiceRoot", "Systems", "StorageSystems"]:
        assert rules[resource]["dynamic"] == False, \
            f"{resource} должен быть dynamic=False"


def test_all_rules_have_required_keys():
    """Каждое правило содержит обязательные ключи"""
    parser = Parser()
    rules = parser.load_rules()
    for name, rule in rules.items():
        assert "endpoint" in rule, f"{name}: нет endpoint"
        assert "expected_status" in rule, f"{name}: нет expected_status"
        assert "required_fields" in rule, f"{name}: нет required_fields"
        assert "spec_section" in rule, f"{name}: нет spec_section"
        assert "spec_url" in rule, f"{name}: нет spec_url"
        assert "dynamic" in rule, f"{name}: нет dynamic"


def test_required_fields_are_dicts():
    """Обязательные поля заданы в виде словаря с метаданными"""
    parser = Parser()
    rules = parser.load_rules()
    for name, rule in rules.items():
        fields = rule["required_fields"]
        assert isinstance(fields, dict), \
            f"{name}: required_fields должен быть словарём"
        for field_name, field_info in fields.items():
            assert "type" in field_info, \
                f"{name}.{field_name}: нет type"
            assert "description" in field_info, \
                f"{name}.{field_name}: нет description"
            assert "spec" in field_info, \
                f"{name}.{field_name}: нет spec"


def test_minimum_15_checks():
    """Суммарное количество проверок >= 15 (требование ТЗ)"""
    parser = Parser()
    rules = parser.load_rules()
    # каждый ресурс даёт минимум: 1 (статус) + 1 (json) + N (поля)
    total = sum(2 + len(rule["required_fields"]) for rule in rules.values())
    assert total >= 15, f"Всего проверок: {total}, нужно >= 15"
