"""
Swordfish API Verifier v1.0
Верификатор соответствия API спецификации Swordfish v1.2.9
"""

import argparse
import logging
import sys
from verifier.config import load_config, ConfigError
from verifier.http_client import HttpClient, HttpClientError
from verifier.parser import Parser
from verifier.validator import Validator
from verifier.reporter import Reporter

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def parse_args():
    """Разбирает аргументы командной строки для неинтерактивного/CI режима."""
    arg_parser = argparse.ArgumentParser(
        description="Swordfish API Verifier -- проверка соответствия API СХД спецификации Swordfish."
    )
    arg_parser.add_argument(
        "--config", default="config.yml",
        help="Путь к конфигурационному YAML файлу (по умолчанию: config.yml)"
    )
    arg_parser.add_argument(
        "--non-interactive", action="store_true",
        help="Запуск без интерактивных вопросов: используются значения из конфига "
             "(schemas_dir/rules_path/resources_filter). Удобно для CI и автотестов."
    )
    arg_parser.add_argument(
        "--resources", default=None,
        help="Список ресурсов через запятую для проверки, например: ServiceRoot,Systems. "
             "Переопределяет resources_filter из конфига."
    )
    return arg_parser.parse_args()


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
    Возвращает список @odata.id систем, под которыми лежат динамические
    ресурсы (StoragePools/Volumes/Drives).

    Сначала пробуем /redfish/v1/StorageSystems (как того требует
    спецификация Swordfish для storage-ресурсов). Если коллекция
    недоступна (ошибка соединения, не-200 статус, пустой список Members)
    -- используем /redfish/v1/Systems как запасной вариант, чтобы
    динамические проверки не пропускались полностью на серверах/эмуляторах,
    которые ещё не реализовали StorageSystems (см. mock_server/broken_server.py).
    """
    for endpoint in ("/redfish/v1/StorageSystems", "/redfish/v1/Systems"):
        try:
            response = client.get(endpoint)
            if response is None or response.status_code != 200:
                continue
            members = response.json().get("Members", [])
            urls = [m["@odata.id"] for m in members if "@odata.id" in m]
            if urls:
                return urls
        except Exception:
            continue
    return []


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
            # id системы нужен всем динамическим ресурсам -- получаем и
            # кешируем его один раз, а не при каждом ресурсе
            if system_urls is None:
                system_urls = get_system_urls(client)

            if not system_urls:
                # раньше это сообщение печаталось только для ПЕРВОГО
                # динамического ресурса, а остальные (например,
                # StoragePools/Volumes/Drives) молча пропадали из вывода,
                # если система недоступна -- теперь сообщаем про каждый
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


def main(args=None):
    if args is None:
        args = parse_args()

    sep()
    print("  SWORDFISH API VERIFIER v1.0")
    print("  Спецификация: Swordfish v1.2.9 (JSON-схемы)")
    sep()

    # ---------- Конфигурация ----------
    try:
        config = load_config(args.config)
    except ConfigError as e:
        print(f"\n  ОШИБКА КОНФИГУРАЦИИ: {e}")
        return 1

    # ---------- Путь к схемам спецификации ----------
    default_spec_path = getattr(config, "schemas_dir", None)

    if args.non_interactive:
        spec_path = default_spec_path
        print(f"  Неинтерактивный режим: использую schemas_dir из конфига: {spec_path}")
    else:
        print("\n  Укажите путь к папке с JSON-схемами SNIA")
        if default_spec_path:
            print(f"  (или нажмите Enter, чтобы использовать schemas_dir из конфига: {default_spec_path}):")
        else:
            print("  (или нажмите Enter, чтобы использовать встроенные правила):")
        spec_path = input("  > ").strip() or default_spec_path

    if not spec_path:
        print("  Использую встроенные правила")
    else:
        print(f"  Буду читать схемы из: {spec_path}")

    # ---------- Подключение к эмулятору ----------
    print(f"\n  Подключение к: {config.emulator_url}")
    client = HttpClient(config)

    try:
        server_available = client.ping()
    except HttpClientError as e:
        print(f"\n  ОШИБКА СОЕДИНЕНИЯ: {e}")
        return 1

    if not server_available:
        print("\n  ОШИБКА: Сервер недоступен.")
        print(f"  Проверьте что эмулятор запущен и адрес в {args.config} верный.")
        return 1
    print("  Сервер доступен ✓")

    # ---------- Загрузка правил ----------
    resources_filter = None
    if args.resources:
        resources_filter = [r.strip() for r in args.resources.split(",") if r.strip()]
    elif getattr(config, "resources_filter", None):
        resources_filter = config.resources_filter

    rules_path = getattr(config, "rules_path", None)

    parser = Parser()
    rules = parser.load_rules(
        spec_path=spec_path,
        resources_filter=resources_filter,
        rules_path=rules_path
    )
    print(f"  Загружено ресурсов: {len(rules)}")

    # ---------- Выбор ресурсов ----------
    if args.non_interactive:
        print(f"  Неинтерактивный режим: проверяются все загруженные ресурсы ({len(rules)}).")
    else:
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

    # ---------- Запуск проверок ----------
    validator = Validator()
    all_results = run_checks(client, validator, rules)

    # ---------- Отчёт ----------
    reporter = Reporter()
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

    # Ненулевой код возврата при провалах или ошибках — удобно для CI.
    return 1 if s["fail"] > 0 else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n  Прервано пользователем.")
        sys.exit(130)
