"""
Валидатор ответов Swordfish API.

Принимает HTTP ответ от эмулятора и правила из parser.py.
Проверяет:
  1. Доступность эндпоинта (response не None)
  2. HTTP статус код
  3. Валидность JSON
  4. Наличие обязательных полей
  5. Типы данных полей
  6. Значения enum-полей (если заданы в схеме)

Возвращает список результатов с PASS / FAIL / NOT_SUPPORTED.

NOT_SUPPORTED используется в двух случаях:
  - ресурс отсутствует и во встроенных правилах, и в загруженной
    спецификации (верификатор не знает, как его проверять);
  - тип поля не удалось определить по спецификации (например, сложный
    $ref, который текущая версия парсера не умеет разворачивать) —
    в этом случае проверка типа не выполняется, чтобы не выдавать
    ложный FAIL.
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
    expected_type
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

    # Конвертируем строковый тип в Python тип если нужно
    if isinstance(expected_type, str):
        type_map = {
            "string": str, "str": str,
            "integer": int, "int": int,
            "number": float, "float": float,
            "array": list, "list": list,
            "object": dict, "dict": dict,
            "boolean": bool, "bool": bool,
        }
        expected_type = type_map.get(expected_type, str)

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


def _resolve_expected_type(expected_type):
    """
    Возвращает Python-тип для проверки или None, если тип не распознан
    (например, парсер не смог определить тип поля по схеме).
    """
    if not expected_type:
        return None

    if isinstance(expected_type, str):
        type_map = {
            "string": str, "str": str,
            "integer": int, "int": int,
            "number": float, "float": float,
            "array": list, "list": list,
            "object": dict, "dict": dict,
            "boolean": bool, "bool": bool,
        }
        return type_map.get(expected_type)

    return expected_type


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

        # Проверка 0: ресурс вообще известен верификатору
        # (нет ни встроенного правила, ни данных из загруженной спецификации)
        if not rule or not rule.get("endpoint"):
            results.append(self._result(
                resource_name, rule or {},
                check="Поддержка ресурса верификатором",
                status="NOT_SUPPORTED",
                detail=(
                    f"Ресурс '{resource_name}' не описан ни во встроенных "
                    f"правилах, ни в загруженной версии спецификации — "
                    f"текущая версия верификатора не может его проверить."
                ),
                expected="описание ресурса в спецификации",
                actual="нет данных"
            ))
            return results

        # Проверка 1: Доступность эндпоинта
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

        # Проверка 3: Валидный JSON
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
                detail="Тело ответа не удалось разобрать как JSON",
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
                    "spec": "...",
                    "enum": ["A", "B"]  # опционально
                },
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
        resolved_type = _resolve_expected_type(expected_type)

        if expected_type and resolved_type is None:
            # Тип указан в схеме, но верификатор не смог его распознать
            # (например, незнакомое имя JSON-типа) — не подставляем
            # str "по умолчанию", а честно сообщаем, что не поддерживаем.
            results.append({
                "check": f"Поле: {field_name}",
                "status": "NOT_SUPPORTED",
                "detail": (
                    f"Тип поля '{field_name}' ('{expected_type}') не "
                    f"распознан текущей версией верификатора — проверка "
                    f"типа пропущена."
                ),
                "expected": f"тип: {expected_type}",
                "actual": str(actual_value),
                "spec_section": spec_section
            })
            continue

        if resolved_type is None:
            # Тип поля вообще не определён по спецификации
            results.append({
                "check": f"Поле: {field_name}",
                "status": "NOT_SUPPORTED",
                "detail": (
                    f"Тип поля '{field_name}' не определён в загруженной "
                    f"версии спецификации — проверка типа не поддерживается "
                    f"текущей версией верификатора."
                ),
                "expected": "тип не определён",
                "actual": str(actual_value),
                "spec_section": spec_section
            })
            continue

        type_valid = validate_field_type(data, field_name, resolved_type)
        if not type_valid:
            expected_name = TYPE_NAMES.get(resolved_type, str(resolved_type))
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

        # 3. Проверка enum, если задан в схеме
        allowed_values = field_info.get("enum") or []
        if allowed_values:
            if not validate_enum(data, field_name, allowed_values):
                results.append({
                    "check": f"Значение поля: {field_name}",
                    "status": "FAIL",
                    "detail": (
                        f"Значение поля '{field_name}' ('{actual_value}') "
                        f"не входит в список допустимых значений спецификации: "
                        f"{allowed_values}."
                    ),
                    "expected": f"одно из: {allowed_values}",
                    "actual": str(actual_value),
                    "spec_section": spec_section
                })
                continue

        # 4. Все проверки пройдены
        results.append({
            "check": f"Поле: {field_name}",
            "status": "PASS",
            "detail": f"Поле '{field_name}' прошло все проверки.",
            "expected": f"тип: {TYPE_NAMES.get(resolved_type, str(resolved_type))}",
            "actual": str(actual_value),
            "spec_section": spec_section
        })

    return results
