"""
Парсер правил проверок для верификатора Swordfish API.
Поддерживает два режима:
  1. Встроенные правила — работают без файлов, всегда доступны
  2. JSON схемы SNIA — автоматический парсинг файлов спецификации

Автоматический парсинг JSON схем реализован через UniversalSchemaParser
"""

import os
import re
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

SPEC_URL = (
    "https://www.snia.org/sites/default/files/technical-work/swordfish/"
    "draft/v1.2.9/html/Specification/Swordfish_v1.2.9_Specification.html"
)

#Перевод типов JSON схем → типы Python
JSON_TYPE_MAP = {
    "string":  str,
    "integer": int,
    "number":  float,
    "array":   list,
    "object":  dict,
    "boolean": bool,
}

# ── Перевод ресурсов → эндпоинты ─────────────────────────────────────────────
# Гриш твой парсер только читает схемы, напрмер для моего main нужны endpoint, вот для этого написна ф-ция
# Здесь указываем для каждого ресурса его URL и тип (статический/динамический).
# dynamic=True означает что эндпоинт зависит от id системы:
#   {system_url} будет заменён на реальный URL в main.py
RESOURCE_ENDPOINTS = {
    "Volume":         {
        "endpoint": "{system_url}/Volumes",
        "dynamic":  True,
        "spec_section": "Таблица 148 — Volume 1.11.0"
    },
    "StoragePool":    {
        "endpoint": "{system_url}/StoragePools",
        "dynamic":  True,
        "spec_section": "Таблица 129 — StoragePool 1.9.2"
    },
    "Drive":          {
        "endpoint": "{system_url}/Drives",
        "dynamic":  True,
        "spec_section": "Раздел 5 — Swordfish Overview"
    },
    "StorageSystem":  {
        "endpoint": "/redfish/v1/StorageSystems",
        "dynamic":  False,
        "spec_section": "Таблица 147 — StorageSystemCollection"
    },
    "ComputerSystem": {
        "endpoint": "/redfish/v1/Systems",
        "dynamic":  False,
        "spec_section": "Раздел 5 — Swordfish Overview"
    },
    "ServiceRoot":    {
        "endpoint": "/redfish/v1/",
        "dynamic":  False,
        "spec_section": "Раздел 8.3 — Discovering Swordfish resources"
    },
}

class UniversalSchemaParser:
    """
    Парсер JSON схем спецификации Swordfish/Redfish.
    Читает файлы вида Volume.v1_11_0.json из папки schemas_dir
    и извлекает правила: обязательные поля, типы, enum значения.
    """

    def __init__(self, schemas_dir: str):
        self.schemas_dir = schemas_dir
        self.rules = {}

    def load_file(self, filepath: str) -> Optional[Dict]:
        """
        Читает JSON файл и возвращает словарь.
        При ошибке логирует и возвращает None.
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки {filepath}: {e}")
            return None

    def get_resource_name(self, filename: str) -> str:
        """
        Извлекает имя ресурса из имени файла.
        Пример: Volume.v1_11_0.json → Volume
        """
        match = re.match(r'([A-Za-z]+)\.v', filename)
        if match:
            return match.group(1)
        return filename.replace('.json', '')

    def extract_definition(self, schema: Dict, resource: str) -> Dict:
        """
        Извлекает определение ресурса из секции definitions.
        Сначала ищет по имени ресурса, если не найдено — берёт первое.
        """
        definitions = schema.get('definitions', {})
        if resource in definitions:
            return definitions[resource]
        if len(definitions) == 1:
            return list(definitions.values())[0]
        return {}

    def extract_field_info(
        self,
        field_name: str,
        field_details: Dict,
        definitions: Dict
    ) -> Dict:
        """
        Извлекает метаданные одного поля: тип, описание, ограничения.
        Разрешает $ref ссылки на другие определения.
        """
        info = {
            "name":         field_name,
            "type":         field_details.get('type', 'unknown'),
            "readonly":     field_details.get('readonly', False),
            "description":  field_details.get('description', ''),
            "versionAdded": field_details.get('versionAdded', '')
        }

        # Дополнительные ограничения
        for key in ('enum', 'format', 'minimum', 'maximum',
                    'minLength', 'maxLength', 'pattern', 'units'):
            if key in field_details:
                info[key] = field_details[key]

        # Разрешаем $ref → берём тип из referenced определения
        if '$ref' in field_details:
            info['$ref'] = field_details['$ref']
            if '#/definitions/' in field_details['$ref']:
                ref_name = field_details['$ref'].replace('#/definitions/', '')
                if ref_name in definitions:
                    ref_def = definitions[ref_name]
                    if 'type' in ref_def:
                        info['type'] = ref_def['type']

        # Для массивов — тип элементов
        if field_details.get('type') == 'array' and 'items' in field_details:
            info['items'] = field_details['items']
            if '$ref' in field_details['items']:
                info['items_type'] = 'object'
            else:
                info['items_type'] = field_details['items'].get('type', 'unknown')

        return info

    def extract_enums(self, definitions: Dict) -> Dict[str, List[str]]:
        """
        Извлекает все enum значения из определений.
        Возвращает словарь: имя_поля → список допустимых значений.
        """
        enums = {}
        for name, definition in definitions.items():
            if 'enum' in definition:
                enums[name] = definition['enum']
            if 'properties' in definition:
                for prop_name, prop_details in definition['properties'].items():
                    if 'enum' in prop_details:
                        enums[f"{name}.{prop_name}"] = prop_details['enum']
        return enums

    def parse_resource(self, filepath: str) -> Optional[Dict]:
        """
        Парсит один файл схемы и возвращает правила для ресурса.
        Возвращает None если файл не удалось прочитать или разобрать.
        """
        filename = os.path.basename(filepath)
        resource = self.get_resource_name(filename)

        schema = self.load_file(filepath)
        if not schema:
            return None

        definitions = schema.get('definitions', {})
        definition = self.extract_definition(schema, resource)
        if not definition:
            logger.warning(f"Не найдено определение для {resource}")
            return None

        properties = definition.get('properties', {})
        fields = {}
        for field_name, field_details in properties.items():
            fields[field_name] = self.extract_field_info(
                field_name, field_details, definitions
            )

        required_fields = definition.get('required', [])
        enums = self.extract_enums(definitions)

        # Извлекаем actions
        actions = {}
        if 'Actions' in definitions:
            actions_def = definitions['Actions']
            for action_name, action_details in \
                    actions_def.get('properties', {}).items():
                if action_name.startswith(f'#{resource}.'):
                    actions[action_name] = {
                        "$ref":        action_details.get('$ref', ''),
                        "description": action_details.get('description', ''),
                        "versionAdded": action_details.get('versionAdded', '')
                    }

        # Извлекаем links
        links = {}
        if 'Links' in definitions:
            links_def = definitions['Links']
            links = {
                "description": links_def.get('description', ''),
                "properties":  {}
            }
            for link_name, link_details in \
                    links_def.get('properties', {}).items():
                links["properties"][link_name] = {
                    "description": link_details.get('description', ''),
                    "type":        link_details.get('type', 'array'),
                    "readonly":    link_details.get('readonly', True)
                }
                if '$ref' in link_details:
                    links["properties"][link_name]['$ref'] = link_details['$ref']
                if 'items' in link_details:
                    links["properties"][link_name]['items'] = link_details['items']

        return {
            "resource":        resource,
            "version":         schema.get('release', 'unknown'),
            "required_fields": required_fields,
            "fields":          fields,
            "enums":           enums,
            "actions":         actions if actions else None,
            "links":           links if links else None
        }

    def get_latest_file(
        self,
        files: List[str],
        resource: str
    ) -> Optional[str]:
        """
        Из нескольких версий файла выбирает самую новую.
        Пример: Volume.v1_9_0.json, Volume.v1_11_0.json → Volume.v1_11_0.json
        """
        latest = None
        latest_version = (-1, -1, -1)

        for filename in files:
            if ':Zone.Identifier' in filename:
                continue
            match = re.search(r'\.v(\d+)\.(\d+)\.(\d+)\.json$', filename)
            if match:
                version = tuple(map(int, match.groups()))
            else:
                version = (0, 0, 0)
            if version > latest_version:
                latest_version = version
                latest = filename

        return latest

    def parse_all(
        self,
        resources_filter: Optional[List[str]] = None
    ) -> Dict:
        """
        Парсит все JSON файлы в schemas_dir.
        resources_filter — если указан, обрабатывает только эти ресурсы.
        Возвращает словарь: имя_ресурса → правила (формат Гриши).
        """
        try:
            all_files = os.listdir(self.schemas_dir)
        except FileNotFoundError:
            logger.error(f"Папка со схемами не найдена: {self.schemas_dir}")
            return {}

        json_files = [
            f for f in all_files
            if f.endswith('.json') and ':Zone.Identifier' not in f
        ]

        # Группируем файлы по имени ресурса
        resources = {}
        for filename in json_files:
            resource = self.get_resource_name(filename)
            if resource not in resources:
                resources[resource] = []
            resources[resource].append(filename)

        # Фильтруем если нужно
        if resources_filter:
            resources = {
                r: files for r, files in resources.items()
                if r in resources_filter
            }

        logger.info(f"Найдено ресурсов: {len(resources)}")

        for resource, files in resources.items():
            latest_file = self.get_latest_file(files, resource)
            if latest_file:
                filepath = os.path.join(self.schemas_dir, latest_file)
                logger.info(f"Парсинг {resource}: {latest_file}")
                rules = self.parse_resource(filepath)
                if rules:
                    self.rules[resource] = rules

        return self.rules


# АДАПТЕР: формат Гриши → формат  validator

def adapt_rules(grgit_rules: Dict) -> Dict:
    """
    Преобразует правила из формата UniversalSchemaParser
    в формат который понимает validator.py.

    Что меняется:
      - required_fields: список строк → словарь с типами и описаниями
      - типы: строки "string"/"integer" → Python типы str/int
      - добавляются endpoint, expected_status, dynamic, spec_section, spec_url
    """
    result = {}

    for resource_name, grgit_rule in grgit_rules.items():

        # Берём endpoint и метаданные 
        # Если ресурса нет в маппинге — строим эндпоинт по имени
        endpoint_info = RESOURCE_ENDPOINTS.get(resource_name, {
            "endpoint":    f"/redfish/v1/{resource_name}s",
            "dynamic":     False,
            "spec_section": f"Ресурс {resource_name}"
        })

        # Преобразуем required_fields из списка в словарь
        # Гриша: ["Id", "Name"]
        # Нам нужно: {"Id": {"type": str, "description": "...", "spec": "..."}}
        required_fields = {}
        grgit_required = grgit_rule.get("required_fields", [])
        all_fields = grgit_rule.get("fields", {})

        for field_name in grgit_required:
            field_info = all_fields.get(field_name, {})
            json_type = field_info.get("type", "string")
            python_type = JSON_TYPE_MAP.get(json_type, str)

            required_fields[field_name] = {
                "type":        python_type,
                "description": field_info.get("description", ""),
                "spec":        endpoint_info.get("spec_section", ""),
            }

        version = grgit_rule.get("version", "unknown")

        result[resource_name] = {
            "endpoint":       endpoint_info["endpoint"],
            "method":         "GET",
            "expected_status": 200,
            "dynamic":        endpoint_info["dynamic"],
            "spec_section":   endpoint_info.get("spec_section", ""),
            "spec_url":       SPEC_URL,
            "spec_version":   version,
            "required_fields": required_fields,
        }

    return result


# ОСНОВНОЙ ПАРСЕР

class Parser:
    """
    Основной парсер правил проверок.

    Поддерживает два режима:
      1. spec_path=None  → встроенные правила (всегда работают)
      2. spec_path=путь  → автоматический парсинг JSON схем SNIA через
                           UniversalSchemaParser

    Использование:
      parser = Parser()

      # Встроенные правила:
      rules = parser.load_rules()

      # Из файлов схем:
      rules = parser.load_rules(spec_path="./specs/schemas")
    """

    def load_rules(
        self,
        spec_path: Optional[str] = None,
        resources_filter: Optional[List[str]] = None
    ) -> Dict:
        """
        Загружает правила проверок.

        :param spec_path: путь к папке с JSON схемами SNIA.
                         Если None — используются встроенные правила.
        :param resources_filter: список ресурсов для фильтрации.
                                Если None — загружаются все ресурсы.
        :return: словарь правил в формате validator.py
        """
        if spec_path:
            return self._load_from_files(spec_path, resources_filter)
        else:
            return self._builtin_rules()

    def _load_from_files(
        self,
        spec_path: str,
        resources_filter: Optional[List[str]] = None
    ) -> Dict:
        """
        Загружает правила из JSON схем через UniversalSchemaParser.
        Если парсинг не дал результатов — падает back на встроенные правила.
        """
        logger.info(f"Загружаю схемы из: {spec_path}")

        grgit_parser = UniversalSchemaParser(spec_path)
        grgit_rules = grgit_parser.parse_all(
            resources_filter=resources_filter
        )

        if not grgit_rules:
            logger.warning(
                "Схемы не найдены или не прочитаны. "
                "Использую встроенные правила."
            )
            return self._builtin_rules()

        # Адаптируем формат к формату нашего validator
        adapted = adapt_rules(grgit_rules)
        logger.info(
            f"Загружено из схем: {len(adapted)} ресурсов"
        )

        # Добавляем встроенные правила для ресурсов которых нет в схемах
        # (например ServiceRoot обычно не идёт отдельным файлом схемы)
        builtin = self._builtin_rules()
        for resource_name, rule in builtin.items():
            if resource_name not in adapted:
                adapted[resource_name] = rule
                logger.info(
                    f"Добавлено из встроенных: {resource_name}"
                )

        return adapted

    def _builtin_rules(self) -> Dict:
        """
        Встроенные правила — написаны вручную на основе спецификации.
        Работают без файлов схем. Всегда доступны.
        """
        return {
            "ServiceRoot": {
                "endpoint":       "/redfish/v1/",
                "method":         "GET",
                "expected_status": 200,
                "spec_section":   "Раздел 8.3 — Discovering Swordfish resources",
                "spec_url":       SPEC_URL,
                "dynamic":        False,
                "required_fields": {
                    "@odata.type": {
                        "type":        str,
                        "description": "Тип ресурса OData",
                        "spec":        "Раздел 7.2 — Schema Considerations"
                    },
                    "@odata.id": {
                        "type":        str,
                        "description": "Уникальный идентификатор ресурса",
                        "spec":        "Раздел 7.2 — Schema Considerations"
                    },
                    "Id": {
                        "type":        str,
                        "description": "Строковый идентификатор ресурса",
                        "spec":        "Таблица 9 — Universal properties"
                    },
                    "Name": {
                        "type":        str,
                        "description": "Имя ресурса",
                        "spec":        "Таблица 9 — Universal properties"
                    },
                    "RedfishVersion": {
                        "type":        str,
                        "description": "Версия Redfish API",
                        "spec":        "Раздел 8.1 — Service Root"
                    }
                }
            },

            "Systems": {
                "endpoint":       "/redfish/v1/Systems",
                "method":         "GET",
                "expected_status": 200,
                "spec_section":   "Раздел 5 — Swordfish Overview",
                "spec_url":       SPEC_URL,
                "dynamic":        False,
                "required_fields": {
                    "@odata.type": {
                        "type":        str,
                        "description": "Тип коллекции OData",
                        "spec":        "Раздел 7.2 — Schema Considerations"
                    },
                    "@odata.id": {
                        "type":        str,
                        "description": "Уникальный идентификатор",
                        "spec":        "Раздел 7.2 — Schema Considerations"
                    },
                    "Members": {
                        "type":        list,
                        "description": "Список систем",
                        "spec":        "Раздел 5 — Swordfish Overview"
                    },
                    "Members@odata.count": {
                        "type":        int,
                        "description": "Количество систем",
                        "spec":        "Раздел 5 — Swordfish Overview"
                    }
                }
            },

            "StorageSystems": {
                "endpoint":       "/redfish/v1/StorageSystems",
                "method":         "GET",
                "expected_status": 200,
                "spec_section":   "Таблица 147 — StorageSystemCollection",
                "spec_url":       SPEC_URL,
                "dynamic":        False,
                "required_fields": {
                    "@odata.type": {
                        "type":        str,
                        "description": "Тип коллекции OData",
                        "spec":        "Раздел 7.2 — Schema Considerations"
                    },
                    "@odata.id": {
                        "type":        str,
                        "description": "Уникальный идентификатор коллекции",
                        "spec":        "Раздел 7.2 — Schema Considerations"
                    },
                    "Members": {
                        "type":        list,
                        "description": "Список систем хранения",
                        "spec":        "Таблица 147 — StorageSystemCollection"
                    },
                    "Members@odata.count": {
                        "type":        int,
                        "description": "Количество систем хранения",
                        "spec":        "Таблица 147 — StorageSystemCollection"
                    }
                }
            },
            "StoragePools": {
                "endpoint":       "{system_url}/StoragePools",
                "method":         "GET",
                "expected_status": 200,
                "spec_section":   "Таблица 129 — StoragePool 1.9.2",
                "spec_url":       SPEC_URL,
                "dynamic":        True,
                "required_fields": {
                    "@odata.type": {
                        "type":        str,
                        "description": "Тип коллекции StoragePool",
                        "spec":        "Таблица 129 — StoragePool 1.9.2"
                    },
                    "@odata.id": {
                        "type":        str,
                        "description": "Уникальный идентификатор коллекции",
                        "spec":        "Раздел 7.2 — Schema Considerations"
                    },
                    "Members": {
                        "type":        list,
                        "description": "Список пулов хранения",
                        "spec":        "Таблица 129 — StoragePool 1.9.2"
                    },
                    "Members@odata.count": {
                        "type":        int,
                        "description": "Количество пулов хранения",
                        "spec":        "Таблица 129 — StoragePool 1.9.2"
                    }
                }
            },

            "Volumes": {
                "endpoint":       "{system_url}/Volumes",
                "method":         "GET",
                "expected_status": 200,
                "spec_section":   "Таблица 148 — Volume 1.11.0",
                "spec_url":       SPEC_URL,
                "dynamic":        True,
                "required_fields": {
                    "@odata.type": {
                        "type":        str,
                        "description": "Тип коллекции Volume",
                        "spec":        "Таблица 148 — Volume 1.11.0"
                    },
                    "@odata.id": {
                        "type":        str,
                        "description": "Уникальный идентификатор коллекции",
                        "spec":        "Раздел 7.2 — Schema Considerations"
                    },
                    "Members": {
                        "type":        list,
                        "description": "Список томов хранения",
                        "spec":        "Таблица 148 — Volume 1.11.0"
                    },
                    "Members@odata.count": {
                        "type":        int,
                        "description": "Количество томов",
                        "spec":        "Таблица 148 — Volume 1.11.0"
                    }
                }
            },

            "Drives": {
                "endpoint":       "{system_url}/Drives",
                "method":         "GET",
                "expected_status": 200,
                "spec_section":   "Раздел 5 — Swordfish Overview",
                "spec_url":       SPEC_URL,
                "dynamic":        True,
                "required_fields": {
                    "@odata.type": {
                        "type":        str,
                        "description": "Тип коллекции Drive",
                        "spec":        "Раздел 5 — Swordfish Overview"
                    },
                    "@odata.id": {
                        "type":        str,
                        "description": "Уникальный идентификатор коллекции",
                        "spec":        "Раздел 7.2 — Schema Considerations"
                    },
                    "Members": {
                        "type":        list,
                        "description": "Список физических дисков",
                        "spec":        "Раздел 5 — Swordfish Overview"
                    },
                    "Members@odata.count": {
                        "type":        int,
                        "description": "Количество дисков",
                        "spec":        "Раздел 5 — Swordfish Overview"
                    }
                }
            }
        }
