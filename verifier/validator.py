"""
Валидатор ответов Swordfish API.

Принимает HTTP ответ от эмулятора и правила из parser.py.
Проверяет:
  1. Доступность эндпоинта (response не None)
  2. HTTP статус код
  3. Валидность JSON
  4. Наличие обязательных полей
  5. Типы данных полей
  6. Enum значения (если указаны в схеме)

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
    bool:  "булево",
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
                             "dynamic": False,
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

        # Конвертируем правила из формата parser в формат validate_resource
        field_rules = []
        for field_name, field_info in required_fields.items():
            field_rules.append({
                "field":          field_name,
                "type":           field_info.get("type"),
                "required":       True,
                "allowed_values": field_info.get("enum", []),
                "description":    field_info.get("description", ""),
                "spec":           field_info.get("spec", rule.get("spec_section", "")),
            })

        # Запускаем проверки полей 
        field_results = validate_resource(body, field_rules)

        # Конвертируем результаты 
        for fr in field_results:
            results.append(self._result(
                resource_name, rule,
                check=f"Поле: {fr['field']}" if fr["status"] == "PASS"
                      else f"{'Обязательное поле' if fr['status'] == 'FAIL' else 'Поле'}: {fr['field']}",
                status=fr["status"],
                detail=fr["message"],
                expected=str(fr["expected"]),
                actual=str(fr["actual"]),
                spec_section=next(
                    (r["spec"] for r in field_rules if r["field"] == fr["field"]),
                    rule.get("spec_section", "")
                )
            ))

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
    rules: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Проверяет JSON ответ по списку правил.

    Принимает:
        data  — словарь из JSON ответа эмулятора
        rules — список правил, каждое правило — словарь:
                {
                  "field":          "Id",
                  "type":           str,
                  "required":       True,
                  "allowed_values": [],     # опционально для enum
                  "description":    "...",
                  "spec":           "..."
                }

    Возвращает:
        список результатов, каждый результат — словарь:
        {
          "field":    "Id",
          "status":   "PASS" / "FAIL" / "NOT_SUPPORTED",
          "message":  "пояснение",
          "expected": "ожидаемое значение",
          "actual":   "фактическое значение"
        }
    """
    results = []

    for rule in rules:
        field_name     = rule.get("field")
        expected_type  = rule.get("type")
        required       = rule.get("required", False)
        allowed_values = rule.get("allowed_values", [])

        if not field_name:
            continue

        field_exists = field_name in data
        actual_value = data.get(field_name) if field_exists else None

        # ── 1. Проверка наличия поля ─────────────────────────────────────────
        if not field_exists:
            if required:
                results.append({
                    "field":    field_name,
                    "status":   "FAIL",
                    "message":  f"Обязательное поле '{field_name}' отсутствует.",
                    "expected": "обязательное поле",
                    "actual":   None
                })
            else:
                results.append({
                    "field":    field_name,
                    "status":   "NOT_SUPPORTED",
                    "message":  f"Необязательное поле '{field_name}' отсутствует.",
                    "expected": "необязательное поле",
                    "actual":   None
                })
            continue

        # Проверка типа данных
        if expected_type:
            type_valid = validate_field_type(data, field_name, expected_type)
            if not type_valid:
                expected_name = TYPE_NAMES.get(expected_type, str(expected_type))
                actual_name   = TYPE_NAMES.get(type(actual_value), str(type(actual_value)))
                results.append({
                    "field":    field_name,
                    "status":   "FAIL",
                    "message":  (
                        f"Поле '{field_name}' имеет неверный тип. "
                        f"Ожидается: {expected_name}, "
                        f"получен: {actual_name} "
                        f"(значение: {actual_value})"
                    ),
                    "expected": expected_name,
                    "actual":   actual_name
                })
                # Если тип неверный — enum не проверяем
                continue

        # Проверка enum значений
        if allowed_values:
            enum_valid = validate_enum(data, field_name, allowed_values)
            if not enum_valid:
                results.append({
                    "field":    field_name,
                    "status":   "FAIL",
                    "message":  (
                        f"Значение поля '{field_name}' не входит "
                        f"в допустимый список: {allowed_values}"
                    ),
                    "expected": str(allowed_values),
                    "actual":   str(actual_value)
                })
                continue

        # Все проверки пройдены
        results.append({
            "field":    field_name,
            "status":   "PASS",
            "message":  f"Поле '{field_name}' прошло все проверки.",
            "expected": (
                f"тип: {TYPE_NAMES.get(expected_type, str(expected_type)) if expected_type else 'любой'}"
                + (f", enum: {allowed_values}" if allowed_values else "")
            ),
            "actual":   str(actual_value)
        })

    return results
