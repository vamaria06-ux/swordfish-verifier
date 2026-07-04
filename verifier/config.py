
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
    specification_path: str
    emulator_url: str
    timeout: int
    output_path: str
    auth: Optional[AuthConfig] = None
    resources_filter: list[str] = field(default_factory=list)
 
 
# Поля, без которых верификатор не может стартовать вообще
REQUIRED_FIELDS = ["specification_path", "emulator_url", "timeout", "output_path"]
 
 
def load_config(path: str = "config.yaml") -> Config:
    """
    Читает YAML-файл по пути `path` и возвращает провалидированный Config.
 
    :raises ConfigError: если файла нет, он пустой, или отсутствует
                          одно из обязательных полей
    """
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Файл конфигурации не найден: {path}")
 
    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
 
    if raw is None:
        raise ConfigError(f"Файл конфигурации пуст: {path}")
 
    missing = [name for name in REQUIRED_FIELDS if name not in raw]
    if missing:
        raise ConfigError(
            f"В config.yaml отсутствуют обязательные поля: {', '.join(missing)}"
        )
 
    spec_path = Path(raw["specification_path"])
    if not spec_path.exists():
        raise ConfigError(
            f"specification_path указывает на несуществующий путь: {spec_path}"
        )
    if not spec_path.is_dir():
        raise ConfigError(
            f"specification_path должен быть директорией со схемами (*.json), "
            f"а не файлом: {spec_path}"
        )
 
    auth_raw = raw.get("auth")
    auth = None
    if auth_raw:
        auth = AuthConfig(
            type=auth_raw.get("type", "basic"),
            username=auth_raw.get("username"),
            password=auth_raw.get("password"),
        )
 
    return Config(
        specification_path=raw["specification_path"],
        emulator_url=raw["emulator_url"],
        timeout=raw["timeout"],
        output_path=raw["output_path"],
        auth=auth,
        resources_filter=raw.get("resources_filter", []),
    )