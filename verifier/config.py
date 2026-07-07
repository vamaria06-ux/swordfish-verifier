from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import yaml 
class ConfigError(Exception):
    """Ошибка конфигурации: файл не найден, пуст или отсутствует обязательное поле."""
@dataclass
class AuthConfig:
    username: str
    password: str
@dataclass
class Config:
    schemas_dir: str
    emulator_url: str
    timeout: int
    output_path: str
    rules_path: str = "data/rules.json"
    auth: Optional[AuthConfig] = None
    resources_filter: list[str] = field(default_factory=list)
    def auth_as_dict(self) -> Optional[dict]:
        """HttpClient ждёт config.auth["username"] — отдаём словарь."""
        if self.auth is None:
            return None
        return {"username": self.auth.username, "password": self.auth.password}
REQUIRED_FIELDS = ["schemas_dir", "emulator_url", "timeout", "output_path"]
 
def load_config(path: str = "config.yaml") -> Config:
    """Загружает YAML-файл и возвращает Config.
    :raises ConfigError: если файла нет, он пустой или отсутствуют обязательные поля."""
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Файл конфигурации не найден: {path}")
    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if raw is None:
        raise ConfigError(f"Файл конфигурации пуст: {path}")
    missing = [name for name in REQUIRED_FIELDS if name not in raw]
    if missing:
        raise ConfigError(f"В config.yaml отсутствуют обязательные поля: {', '.join(missing)}")
 
    schemas_dir = Path(raw["schemas_dir"])
    if not schemas_dir.exists():
        raise ConfigError(f"schemas_dir указывает на несуществующий путь: {schemas_dir}")
    if not schemas_dir.is_dir():
        raise ConfigError(f"schemas_dir должен быть директорией со схемами (*.json), "
            f"а не файлом: {schemas_dir}")
 
    auth = None
    auth_raw = raw.get("auth")
    if auth_raw:
        auth = AuthConfig(
            username=auth_raw["username"],
            password=auth_raw["password"],)
 
    return Config(
        schemas_dir=raw["schemas_dir"],
        emulator_url=raw["emulator_url"],
        timeout=raw["timeout"],
        output_path=raw["output_path"],
        rules_path=raw.get("rules_path", "data/rules.json"),
        auth=auth,
        resources_filter=raw.get("resources_filter", []),)

