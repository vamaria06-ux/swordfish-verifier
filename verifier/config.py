"""
config.py — читает config.yaml и отдаёт настройки остальным модулям.

Ничего не знает про parser.py и http_client.py — просто парсит YAML,
проверяет, что обязательные поля на месте, и возвращает готовый объект
с настройками. Дальше этот объект передаётся в http_client.py (url,
timeout, auth) и в parser.py (version, filters) — каждому своё.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import yaml


class ConfigError(Exception):
    """Ошибка конфигурации: файл не найден, пуст или не хватает обязательного поля."""


@dataclass
class EmulatorConfig:
    url: str
    timeout: int = 10


@dataclass
class AuthConfig:
    type: str = "basic"
    username: Optional[str] = None
    password: Optional[str] = None


@dataclass
class SpecificationConfig:
    version: str = "1.2.9"


@dataclass
class FiltersConfig:
    resources: list[str] = field(default_factory=list)


@dataclass
class Config:
    emulator: EmulatorConfig
    auth: AuthConfig
    specification: SpecificationConfig
    filters: FiltersConfig


def load_config(path: str = "config.yaml") -> Config:
    """
    Читает YAML-файл по пути `path` и возвращает провалидированный Config.

    :raises ConfigError: если файла нет, он пустой, или отсутствует
                          обязательное поле emulator.url
    """
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Файл конфигурации не найден: {path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raise ConfigError(f"Файл конфигурации пуст: {path}")

    emulator_raw = raw.get("emulator")
    if not emulator_raw or "url" not in emulator_raw:
        raise ConfigError(
            "В config.yaml отсутствует обязательное поле emulator.url — "
            "без него http_client.py не будет знать, куда стучаться"
        )

    auth_raw = raw.get("auth") or {}
    spec_raw = raw.get("specification") or {}
    filters_raw = raw.get("filters") or {}

    return Config(
        emulator=EmulatorConfig(
            url=emulator_raw["url"],
            timeout=emulator_raw.get("timeout", 10),
        ),
        auth=AuthConfig(
            type=auth_raw.get("type", "basic"),
            username=auth_raw.get("username"),
            password=auth_raw.get("password"),
        ),
        specification=SpecificationConfig(
            version=spec_raw.get("version", "1.2.9"),
        ),
        filters=FiltersConfig(
            resources=filters_raw.get("resources", []),
        ),
    )