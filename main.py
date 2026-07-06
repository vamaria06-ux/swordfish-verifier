"""
Swordfish API Verifier v1.0
Верификатор соответствия API спецификации Swordfish v1.2.9
"""

import logging
import sys
from verifier.config import Config
from verifier.http_client import HttpClient
from verifier.parser import Parser
from verifier.validator import Validator
from verifier.reporter import Reporter

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def sep():
    print("─" * 60)


def menu(title, options):
    """
    Показывает меню и возвращает выбор пользователя.
    options — список строк с вариантами.
    """
    print(f"\n{title}")
    for i, option in enumerate(options, 1):
        print(f"  {i}. {option}")
    while True:
        choice = input("> ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return int(choice)
        print(f"  Введите число от 1 до {len(options)}")


def get_system_urls(client):
    """
    Получает список URL всех систем хранения из StorageSystems.
    Нужно для динамических ресурсов: StoragePools, Volumes, Drives.
    """
    response = client.get("/redfish/v1/StorageSystems")
    if response is None:
        return []
    members = response.json().get("Members", [])
    return [m["@odata.id"] for m in members if "@odata.id" in m]


def select_resources(rules):
    """
    Даёт пользователю выбрать какие ресурсы проверять.
    Возвращает отфильтрованный словарь правил.
    """
    names = list(rules.keys())
    print("\nДоступные ресурсы:")
    for i, name in enumerate(names, 1):
        rule = rules[name]
        endpoint = rule["endpoint"].replace("{system_url}", "/redfish/v1/StorageSystems/{id}")
        print(f"  {i}. {name:<20} {endpoint}")

    print("\nВведите номера через запятую (или Enter для всех):")
    raw = input("> ").strip()

    if not raw:
        return rules

    selected = {}
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit() and 1 <= int(part) <= len(names):
            name = names[int(part) - 1]
            selected[name] = rules[name]

    return selected if selected else rules


def run_checks(client, validator, rules):
    """
    Запускает все проверки.
    Для динамических ресурсов сначала получает id систем.
    Возвращает список всех результатов.
    """
    all_results = []
    system_urls = None  # загрузим только если понадобится

    for resource_name, rule in rules.items():
        if rule.get("dynamic"):
            # нужен id системы — получаем список систем
            if system_urls is None:
                system_urls = get_system_urls(client)
                if not system_urls:
                    sep()
                    print(f"  {resource_name} — пропущен")
                    print("  Нет доступных StorageSystems для проверки")
                    continue

            # проверяем для каждой системы
            for system_url in system_urls:
                endpoint = rule["endpoint"].replace("{system_url}", system_url)
                actual_rule = dict(rule)
                actual_rule["endpoint"] = endpoint
                actual_resource_name = f"{resource_name} ({system_url})"

                sep()
                print(f"  {actual_resource_name}")
                print(f"  {endpoint}")
                sep()

                response = client.get(endpoint)
                results = validator.validate(response, actual_rule, actual_resource_name)
                all_results.extend(results)

                for r in results:
                    _print_result(r)

        else:
            # статичный эндпоинт
            sep()
            print(f"  {resource_name}")
            print(f"  {rule['endpoint']}")
            sep()

            response = client.get(rule["endpoint"])
            results = validator.validate(response, rule, resource_name)
            all_results.extend(results)

            for r in results:
                _print_result(r)

    return all_results


def _print_result(r):
    """Выводит одну строку результата проверки."""
    if r["status"] == "PASS":
        print(f"  ✓  PASS  |  {r['check']}")
    elif r["status"] == "FAIL":
        print(f"  ✗  FAIL  |  {r['check']}")
        print(f"           |  {r['detail']}")
        print(f"           |  Спецификация: {r['spec_section']}")
    else:
        print(f"  ?  N/S   |  {r['check']}")


def main():
    sep()
    print("  SWORDFISH API VERIFIER v1.0")
    print("  Спецификация: Swordfish v1.2.9")
    sep()

    # 1. Версия спецификации
    choice = menu("Выберите версию спецификации:", [
        "Swordfish v1.2.9 (рекомендуется)",
        "Swordfish v1.2.8",
        "Swordfish v1.2.7"
    ])
    versions = {1: "1.2.9", 2: "1.2.8", 3: "1.2.7"}
    spec_version = versions[choice]
    print(f"  Выбрана версия: Swordfish v{spec_version}")

    # 2. Формат спецификации 
    fmt_choice = menu("Выберите формат спецификации:", [
        "JSON схемы (рекомендуется)",
        "YAML",
        "XML",
        "Встроенные правила (без файлов)"
    ])
    formats = {1: "JSON", 2: "YAML", 3: "XML", 4: "Встроенные"}
    spec_format = formats[fmt_choice]
    print(f"  Выбран формат: {spec_format}")

    spec_path = None
    if fmt_choice in (1, 2, 3):
        print(f"\n  Укажите путь к папке с JSON схемами SNIA")
        print(f"  (или Enter чтобы использовать встроенные правила):")
        entered_path = input("  > ").strip()
        if entered_path:
            spec_path = entered_path
            print(f"  Буду читать схемы из: {spec_path}")
        else:
            print("  Использую встроенные правила")

    #  3. Подключение к эмулятору 
    config = Config("config.yml", 30, "output")
    print(f"\n  Подключение к: {config.emulator_url}")
    client = HttpClient(config)

    if not client.ping():
        print("\n  ОШИБКА: Сервер недоступен.")
        print("  Проверьте что эмулятор запущен и адрес в config.yml верный.")
        sys.exit(1)
    print("  Сервер доступен ✓")

    #  4. Загрузка правил 
    parser = Parser()
    rules = parser.load_rules(spec_path=spec_path)
    print(f"  Загружено ресурсов: {len(rules)}")

    # 5. Выбор ресурсов 
    resource_choice = menu("Что проверять?", [
        "Все ресурсы (рекомендуется)",
        "Только базовые (ServiceRoot, Systems, StorageSystems)",
        "Выбрать вручную"
    ])

    if resource_choice == 2:
        rules = {k: v for k, v in rules.items()
                 if k in ("ServiceRoot", "Systems", "StorageSystems")}
    elif resource_choice == 3:
        rules = select_resources(rules)

    print(f"\n  Будет проверено ресурсов: {len(rules)}")

    # 6. Запуск проверок
    validator = Validator()
    all_results = run_checks(client, validator, rules)

    # 7. Отчёт
    report = reporter.generate(all_results, config)

    s = report["summary"]
    print("\n")
    sep()
    print("  ИТОГ")
    sep()
    print(f"  Всего проверок:  {s['total']}")
    print(f"  PASS:            {s['pass']}")
    print(f"  FAIL:            {s['fail']}")
    print(f"  NOT_SUPPORTED:   {s['not_supported']}")
    print(f"  Процент успеха:  {s['pass_rate']}")
    sep()
    print(f"\n  Отчёт сохранён: {config.output_path}/report.json\n")


if __name__ == "__main__":
    main()
