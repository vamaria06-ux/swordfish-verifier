import json
from typing import Dict, Any, Type, List, Union

# Проверяет наличие обязательного поля в JSON-ответе.
def validate_required_field(data: Dict[str, Any], field_name: str) -> bool:
    return field_name in data

# Проверяет, что поле существует и имеет правильный тип.
def validate_field_type(data: Dict[str, Any], field_name: str, expected_type: Type) -> bool:

    if field_name not in data:
        return False

    value = data[field_name]

    if expected_type == int:
        return isinstance(value, int) and not isinstance(value, bool)
    elif expected_type == float:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    else:
        return isinstance(value, expected_type)

# Проверяет, что значение поля входит в список разрешённых значений.
def validate_enum(data: Dict[str, Any], field_name: str, allowed_values: List[str]) -> bool:
    if field_name not in data:
        return False

    value = data[field_name]

    if not isinstance(value, str):
        return False

    return value in allowed_values

# Проверяет JSON-ответ по списку правил.
def validate_resource(data: Dict[str, Any], rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Проверяет JSON-ответ по списку правил.
    
    Аргументы:
        data (dict): JSON-ответ от эмулятора.
        rules (list): Список правил для этого ресурса.
                      Каждое правило — словарь с полями:
                      - field: имя поля
                      - type: ожидаемый тип (str, int, bool, ...)
                      - required: True/False
                      - allowed_values: список значений для enum (опционально)
    
    Возвращает:
        list: Список результатов проверок. Каждый результат — словарь:
              - field: имя поля
              - status: "PASS" / "FAIL" / "NOT_SUPPORTED"
              - message: пояснение
              - expected: ожидаемое значение
              - actual: фактическое значение
    """
    results = []

    for rule in rules:
        field_name = rule.get("field")
        expected_type = rule.get("type")
        required = rule.get("required", False)
        allowed_values = rule.get("allowed_values", [])

        # Пропускаем правила без имени поля
        if not field_name:
            continue

        # Проверяем, есть ли поле
        field_exists = field_name in data
        actual_value = data.get(field_name) if field_exists else None

        # --- 1. Проверка наличия поля ---
        if not field_exists:
            if required:
                results.append({
                    "field": field_name,
                    "status": "FAIL",
                    "message": f"Обязательное поле '{field_name}' отсутствует.",
                    "expected": "обязательное поле",
                    "actual": None
                })
            else:
                results.append({
                    "field": field_name,
                    "status": "NOT_SUPPORTED",
                    "message": f"Необязательное поле '{field_name}' отсутствует.",
                    "expected": "необязательное поле",
                    "actual": None
                })
            continue

        # --- 2. Проверка типа данных ---
        if expected_type:
            type_valid = validate_field_type(data, field_name, expected_type)
            if not type_valid:
                results.append({
                    "field": field_name,
                    "status": "FAIL",
                    "message": f"Поле '{field_name}' имеет неверный тип. Ожидается: {expected_type.__name__}, получен: {type(actual_value).__name__}",
                    "expected": expected_type.__name__,
                    "actual": type(actual_value).__name__
                })
                continue  # Если тип неверный, enum не проверяем

        # --- 3. Проверка перечисления (enum) ---
        if allowed_values:
            enum_valid = validate_enum(data, field_name, allowed_values)
            if not enum_valid:
                results.append({
                    "field": field_name,
                    "status": "FAIL",
                    "message": f"Значение поля '{field_name}' не входит в допустимый список: {allowed_values}",
                    "expected": allowed_values,
                    "actual": actual_value
                })
                continue

        # --- 4. Если все проверки пройдены ---
        results.append({
            "field": field_name,
            "status": "PASS",
            "message": f"Поле '{field_name}' прошло все проверки.",
            "expected": f"тип: {expected_type.__name__ if expected_type else 'любой'}" + (f", enum: {allowed_values}" if allowed_values else ""),
            "actual": actual_value
        })

    return results
