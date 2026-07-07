"""
Валидатор ответов Swordfish API.

Принимает HTTP ответ от эмулятора и правила из parser.py.
Проверяет:
  1. Доступность эндпоинта (response не None)
  2. HTTP статус код
  3. Валидность JSON
  4. Наличие обязательных полей
  5. Типы данных полей

Возвращает список результатов с PASS / FAIL / NOT_SUPPORTED.
"""

import logging
from typing import Dict, Any, Type, List, Optional

logger = logging.getLogger(__name__)

TYPE_NAMES = {
    str:   "строка",
    int:   "целое число",
    float: "число",
    list:  "список",
    dict:  "объект",
    bool:  "логическое",
}

def validate_required_field(data: Dict[str, Any], field_name: str) -> bool:
    """
    Проверяет наличие поля в JSON ответе.

    Принимает:
        data       — словарь из JSON ответа эмулятора
        field_name — имя поля которое ищем

    Возвращает:
        True если поле есть, False если нет
    """
    return field_name in data


def validate_field_type(
    data: Dict[str, Any],
    field_name: str,
    expected_type: Type
) -> bool:
    """
    Проверяет что поле существует и имеет правильный тип.
    Принимает:
        data          — словарь из JSON ответа
        field_name    — имя поля
        expected_type — ожидаемый Python тип (str, int, list, dict, bool)

    Возвращает:
        True если поле есть и тип верный, False иначе
    """
    if field_name not in data:
        return False

    value = data[field_name]

    if expected_type == int:
        # True и False — это bool, не int, хотя isinstance(True, int) = True
        return isinstance(value, int) and not isinstance(value, bool)
    elif expected_type == float:
        # float принимаем и int и float, но не bool
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    else:
        return isinstance(value, expected_type)


def validate_enum(
    data: Dict[str, Any],
    field_name: str,
    allowed_values: List[str]
) -> bool:
    """
    Проверяет что значение поля входит в список разрешённых значений.

    Принимает:
        data           — словарь из JSON ответа
        field_name     — имя поля
        allowed_values — список допустимых значений

    Возвращает:
        True если значение входит в список, False иначе
    """
    if field_name not in data:
        return False

    value = data[field_name]

    if not isinstance(value, str):
        return False

    return value in allowed_values

class Validator:
    """
    Валидатор ответов Swordfish API.

    Принимает ответ от http_client и правила из parser.
    Возвращает список результатов проверок.
    """

    def validate(
        self,
        response,
        rule: Dict,
        resource_name: str
    ) -> List[Dict]:
        """
        Проверяет HTTP ответ по правилам из parser.py.

        Принимает:
            response      — объект Response от http_client,
                           или None если сервер недоступен
            rule          — словарь правил из parser.py:
                           {
                             "endpoint": "/redfish/v1/",
                             "expected_status": 200,
                             "spec_section": "...",
                             "required_fields": {
                               "Id": {"type": str, "description": "...", "spec": "..."},
                               ...
                             }
                           }
            resource_name — название ресурса для отчёта ("ServiceRoot", ...)

        Возвращает:
            список словарей, каждый из которых описывает одну проверку:
            {
              "resource":     "ServiceRoot",
              "check":        "HTTP статус код",
              "status":       "PASS" / "FAIL" / "NOT_SUPPORTED",
              "endpoint":     "/redfish/v1/",
              "detail":       "Получен 200 — соответствует ожидаемому",
              "expected":     "200",
              "actual":       "200",
              "spec_section": "Раздел 8.5 — HTTP status codes",
              "spec_url":     "https://snia.org/..."
            }
        """
        results = []

        #Проверка 1: Доступность эндпоинта
        if response is None:
            results.append(self._result(
                resource_name, rule,
                check="Доступность эндпоинта",
                status="FAIL",
                detail="Сервер недоступен или нет соединения",
                expected="ответ от сервера",
                actual="нет ответа"
            ))
            return results

        # Проверка 2: HTTP статус код
        expected_status = rule.get("expected_status", 200)
        if response.status_code == expected_status:
            results.append(self._result(
                resource_name, rule,
                check="HTTP статус код",
                status="PASS",
                detail=f"Получен {response.status_code} — соответствует ожидаемому",
                expected=str(expected_status),
                actual=str(response.status_code),
                spec_section="Раздел 8.5 — HTTP status codes"
            ))
        else:
            results.append(self._result(
                resource_name, rule,
                check="HTTP статус код",
                status="FAIL",
                detail=(
                    f"Ожидался {expected_status}, получен {response.status_code}. "
                    f"По спецификации GET запрос к существующему ресурсу "
                    f"должен возвращать 200."
                ),
                expected=str(expected_status),
                actual=str(response.status_code),
                spec_section="Раздел 8.5 — HTTP status codes"
            ))

        #Проверка 3: Валидный JSON
        try:
            body = response.json()
            results.append(self._result(
                resource_name, rule,
                check="Ответ является валидным JSON",
                status="PASS",
                detail="JSON успешно распарсен",
                expected="валидный JSON",
                actual="валидный JSON",
                spec_section="Раздел 7 — Schema Considerations"
            ))
        except Exception:
            results.append(self._result(
                resource_name, rule,
                check="Ответ является валидным JSON",
                status="FAIL",
                detail=(
                    "Ответ не является валидным JSON. "
                    "Все ответы Swordfish API должны быть в формате JSON."
                ),
                expected="валидный JSON",
                actual="невалидный ответ",
                spec_section="Раздел 7 — Schema Considerations"
            ))
            # Дальше проверять поля нет смысла — нет JSON
            return results

        # Проверки 4-6: Поля из правил
        required_fields = rule.get("required_fields", {})

        # Запускаем проверки полей 
        field_results = validate_resource(body, required_fields)

        # Конвертируем результаты 
        for fr in field_results:
            results.append({
                "resource": resource_name,
                "check": fr["check"],
                "status": fr["status"],
                "endpoint": rule.get("endpoint", ""),
                "detail": fr["detail"],
                "expected": str(fr["expected"]),
                "actual": str(fr["actual"]),
                "spec_section": fr.get("spec_section", rule.get("spec_section", "")),
                "spec_url": rule.get("spec_url", "")
            })

        return results

    def _result(
        self,
        resource_name: str,
        rule: Dict,
        check: str,
        status: str,
        detail: str,
        expected: str = "",
        actual: str = "",
        spec_section: Optional[str] = None
    ) -> Dict:
        """
        Вспомогательный метод — создаёт словарь результата проверки.
        Используется внутри validate() чтобы не дублировать структуру словаря.

        Принимает все поля результата.
        Возвращает словарь в стандартном формате.
        """
        return {
            "resource":     resource_name,
            "check":        check,
            "status":       status,
            "endpoint":     rule.get("endpoint", ""),
            "detail":       detail,
            "expected":     expected,
            "actual":       actual,
            "spec_section": spec_section or rule.get("spec_section", ""),
            "spec_url":     rule.get("spec_url", ""),
        }


def validate_resource(
    data: Dict[str, Any],
    required_fields: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Проверяет JSON ответ по списку правил.

    Принимает:
        data  — словарь из JSON ответа эмулятора
        required_fields  — словарь обязательных полей от парсера:
            {
                "Id": {
                    "type": str,
                    "description": "...",
                    "spec": "..."},
            }

    Возвращает:
        список словарей, каждый из которых описывает одну проверку поля:
        {
            "check":        "Поле: Id",
            "status":       "PASS" / "FAIL" / "NOT_SUPPORTED",
            "detail":       "пояснение",
            "expected":     "ожидаемое значение",
            "actual":       "фактическое значение",
            "spec_section": "Раздел 7.2 — Schema Considerations",
        }
    """
    results = []

    for field_name, field_info in required_fields.items():
        expected_type = field_info.get("type")
        spec_section = field_info.get("spec", "")

        field_exists = field_name in data
        actual_value = data.get(field_name) if field_exists else None

        # 1. Проверка наличия поля
        if not field_exists:
            results.append({
                "check": f"Обязательное поле: {field_name}",
                "status": "FAIL",
                "detail": f"Обязательное поле '{field_name}' отсутствует.",
                "expected": "обязательное поле",
                "actual": None,
                "spec_section": spec_section
            })
            continue

        # 2. Проверка типа данных
        if expected_type:
            type_valid = validate_field_type(data, field_name, expected_type)
            if not type_valid:
                expected_name = TYPE_NAMES.get(expected_type, str(expected_type))
                actual_name = TYPE_NAMES.get(type(actual_value), str(type(actual_value)))
                results.append({
                    "check": f"Поле: {field_name}",
                    "status": "FAIL",
                    "detail": (
                        f"Поле '{field_name}' имеет неверный тип. "
                        f"Ожидается: {expected_name}, "
                        f"получен: {actual_name} "
                        f"(значение: {actual_value})"
                    ),
                    "expected": expected_name,
                    "actual": actual_name,
                    "spec_section": spec_section
                })
                continue

        # 3. Все проверки пройдены
        results.append({
            "check": f"Поле: {field_name}",
            "status": "PASS",
            "detail": f"Поле '{field_name}' прошло все проверки.",
            "expected": f"тип: {TYPE_NAMES.get(expected_type, str(expected_type)) if expected_type else 'любой'}",
            "actual": str(actual_value),
            "spec_section": spec_section
        })

    return results
