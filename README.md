# Swordfish API Verifier

Верификатор соответствия REST API систем хранения данных (СХД) спецификации
[SNIA Swordfish](https://www.snia.org/forums/smi/swordfish) v1.2.9.

Инструмент подключается к эмулятору/реальному API СХД, автоматически строит
правила проверки на основе JSON-схем SNIA (или встроенных правил), выполняет
запросы к ключевым ресурсам (ServiceRoot, Systems, StorageSystems,
StoragePools, Volumes, Drives) и формирует отчёт со статусами `PASS`,
`FAIL` и `NOT_SUPPORTED` по каждой проверке.

## Возможности

- Автоматический парсинг JSON-схем SNIA (`verifier/parser.py`,
  `UniversalSchemaParser`) с извлечением обязательных полей, типов, enum
  значений и эндпоинтов.
- Встроенные (fallback) правила для базовых ресурсов — верификатор работает
  даже без файлов схем.
- HTTP-клиент с поддержкой Basic Auth и таймаутов (`verifier/http_client.py`).
- Валидатор с тремя статусами проверки: `PASS`, `FAIL`, `NOT_SUPPORTED`
  (ресурс/поле, которые верификатор не может корректно проверить, честно
  помечаются как `NOT_SUPPORTED`, а не пропускаются молча).
- Генератор JSON-отчёта со сводкой (`verifier/reporter.py`).
- Интерактивный режим (пошаговое меню) и неинтерактивный режим для CI/CD
  (`--non-interactive`).
- Mock-сервер с намеренными ошибками (`mock_server/broken_server.py`) для
  проверки самого верификатора.
- Юнит-тесты для парсера, валидатора и генератора отчётов + CI (GitHub
  Actions, `pytest`).

## Установка

Требуется Python 3.11+.

```bash
git clone https://github.com/vamaria06-ux/swordfish-verifier.git
cd swordfish-verifier
pip install -r requirements.txt
```

## Конфигурация

Настройки верификатора задаются в YAML-файле (по умолчанию `config.yml`):

| Поле               | Обязательное | Описание                                                            |
|---------------------|:------------:|----------------------------------------------------------------------|
| `schemas_dir`       | да  | Папка с JSON-схемами SNIA (например, `data/schemas/json-schema`)     |
| `emulator_url`      | да  | Адрес проверяемого API СХД/эмулятора                                 |
| `timeout`           | да  | Таймаут HTTP-запросов, сек                                            |
| `output_path`       | да  | Папка для сохранения `report.json`                                   |
| `rules_path`        | нет | Путь к заранее сохранённому файлу правил (`Parser.save_rules`)        |
| `auth`              | нет | `username`/`password` для Basic Auth                                 |
| `resources_filter` | нет | Список ресурсов для проверки; если не задан — проверяются строго 6 базовых ресурсов (ServiceRoot, Systems, StorageSystems, StoragePools, Volumes, Drives) |

В репозитории есть два готовых конфига:

- `config.yml` — для работы с полноценным эмулятором Swordfish.
- `config_mock.yml` — для работы с mock-сервером `mock_server/broken_server.py`.

## Запуск

### 1. Mock-сервер (для быстрой проверки без реального эмулятора)

```bash
python mock_server/broken_server.py
```

Сервер поднимется на `http://localhost:5001` и намеренно отдаёт несколько
некорректных ответов — удобно, чтобы увидеть все три статуса (`PASS`,
`FAIL`, `NOT_SUPPORTED`) в отчёте.

### 2. Верификатор

Интерактивный режим:

```bash
python main.py --config config_mock.yml
```

Неинтерактивный режим (для CI/автоматизации, без вопросов в консоли):

```bash
python main.py --config config_mock.yml --non-interactive
```

Проверка только конкретных ресурсов:

```bash
python main.py --config config.yml --non-interactive --resources ServiceRoot,Systems
```

Верификатор завершается с кодом `0`, если проваленных проверок нет, и с
кодом `1`, если есть `FAIL` или ошибка конфигурации/соединения — это
позволяет использовать его как шаг в CI.

Отчёт сохраняется в `<output_path>/report.json`.

## Тестирование

```bash
pytest tests/ -v
```

Тесты покрывают: генератор отчётов (`tests/test_reporter.py`), парсер правил
(`tests/test_parser.py`), валидатор и статус `NOT_SUPPORTED`
(`tests/test_validator.py`), HTTP-клиент (`tests/test_http_client.py`),
конфигурацию (`tests/test_config.py`) и базовую интеграцию с mock-сервером
(`tests/test_mock_integration.py`, `tests/test_basic.py`).

CI (GitHub Actions, `.github/workflows/ci.yml`) автоматически запускает
`pytest` на каждый pull request в `main`.

## Структура проекта

```
main.py                     Точка входа (интерактивный и CLI режимы)
verifier/
  config.py                 Загрузка и валидация config.yml
  http_client.py             HTTP-клиент к проверяемому API
  parser.py                  Парсер JSON-схем SNIA + встроенные правила
  validator.py                Проверка ответов API, статусы PASS/FAIL/NOT_SUPPORTED
  reporter.py                 Сборка итогового JSON-отчёта
mock_server/
  broken_server.py            Mock-сервер с намеренными ошибками для тестов
data/
  schemas/json-schema/        JSON-схемы спецификации SNIA Swordfish
tests/                       Юнит-тесты
config.yml / config_mock.yml Примеры конфигурации
```

## Известные ограничения

- Mock-сервер (`mock_server/broken_server.py`) покрывает все 6 базовых ресурсов: `ServiceRoot`, `Systems`, `StorageSystems`, а также динамические `StoragePools`/`Volumes`/`Drives` под `/redfish/v1/StorageSystems/1/...` (для их обнаружения `main.py` при недоступном `StorageSystems` использует `Systems` как запасной источник id системы).
- Автоматический парсинг спецификации поддерживает только формат JSON-схем
  SNIA; PDF/XML/YML версии спецификации не разбираются.
