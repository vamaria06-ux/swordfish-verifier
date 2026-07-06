from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import yaml


class ConfigError(Exception):
    """Ошибка конфигурации: файл не найден, пуст или не хватает обязательного поля."""


@dataclass
class AuthConfig:
    type: str = "basic"
    username: Optional[str] = None
    password: Optional[str] = None


@dataclass
class Config:
    """
    Конфигурация верификатора.

    Поля:
        emulator_url      — адрес Swordfish API эмулятора
        timeout           — таймаут HTTP запросов в секундах
        output_path       — папка для сохранения отчётов
        specification_path— путь к папке с JSON схемами SNIA (необязательно)
                            если не указан — используются встроенные правила
        auth              — настройки аутентификации (необязательно)
        resources_filter  — список ресурсов для проверки (необязательно)
                            если пустой — проверяются все ресурсы
    """
    emulator_url: str
    timeout: int
    output_path: str
    specification_path: Optional[str] = None
    auth: Optional[AuthConfig] = None
    resources_filter: list[str] = field(default_factory=list)


# Поля без которых верификатор не может запуститься
REQUIRED_FIELDS = ["emulator_url", "timeout", "output_path"]


def load_config(path: str = "config.yml") -> Config:
    """
    Читает YAML-файл по пути `path` и возвращает валидный Config.

    Что принимает:
        path — путь к файлу конфигурации (по умолчанию "config.yml")

    Что возвращает:
        объект Config со всеми настройками

    Что проверяет:
        - файл существует
        - файл не пустой
        - все обязательные поля заполнены (emulator_url, timeout, output_path)
        - если specification_path указан — папка существует и является директорией

    :raises ConfigError: если файла нет, он пустой, или отсутствуют обязательные поля
    """
    config_path = Path(path)

    if not config_path.exists():
        raise ConfigError(f"Файл конфигурации не найден: {path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raise ConfigError(f"Файл конфигурации пуст: {path}")

    # Проверяем обязательные поля
    missing = [name for name in REQUIRED_FIELDS if name not in raw]
    if missing:
        raise ConfigError(
            f"В конфигурации отсутствуют обязательные поля: {', '.join(missing)}"
        )

    # Проверяем specification_path только если он указан
    spec_path_str = raw.get("specification_path")
    if spec_path_str:
        spec_path = Path(spec_path_str)
        if not spec_path.exists():
            raise ConfigError(
                f"specification_path указывает на несуществующий путь: {spec_path}"
            )
        if not spec_path.is_dir():
            raise ConfigError(
                f"specification_path должен быть директорией со схемами (*.json), "
                f"а не файлом: {spec_path}"
            )

    # Собираем auth если указан
    auth_raw = raw.get("auth")
    auth = None
    if auth_raw:
        auth = AuthConfig(
            type=auth_raw.get("type", "basic"),
            username=auth_raw.get("username"),
            password=auth_raw.get("password"),
        )

    return Config(
        emulator_url=raw["emulator_url"],
        timeout=raw["timeout"],
        output_path=raw["output_path"],
        specification_path=spec_path_str,
        auth=auth,
        resources_filter=raw.get("resources_filter", []),
    )
