import json
from typing import Dict, Any, Type

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

