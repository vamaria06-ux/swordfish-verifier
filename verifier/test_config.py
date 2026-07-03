
"""Тесты для config.py"""
 
import pytest
from pathlib import Path
from config import load_config, ConfigError
 
 
def test_load_valid_config(tmp_path):
    """Correct config.yaml starting and working no fail """
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
emulator:
  url: "http://localhost:8080"
  timeout: 10
auth:
  type: "basic"
  username: "admin"
  password: "admin"
specification:
  version: "1.2.9"
filters:
  resources:
    - "StoragePools"
""")
    config = load_config(str(config_file))
 
    assert config.emulator.url == "http://localhost:8080"
    assert config.emulator.timeout == 10
    assert config.auth.username == "admin"
    assert config.specification.version == "1.2.9"
    assert config.filters.resources == ["StoragePools"]
 
 
def test_missing_file_raises_error():
    """Have not fiel  — error should be informative and clear, no fail"""
    with pytest.raises(ConfigError, match="не найден"):
        load_config("not exist -> load mistake.yaml")
 
 
def test_empty_file_raises_error(tmp_path):
    """Empty fiel — config wrong due to none in"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("")
 
    with pytest.raises(ConfigError, match="пуст"):
        load_config(str(config_file))
 
 
def test_missing_url_raises_error(tmp_path):
    """No emulator.url http_client.py no address to config"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
emulator:
  timeout: 10
""")
    with pytest.raises(ConfigError, match="emulator.url"):
        load_config(str(config_file))
 
 
def test_defaults_applied_when_optional_fields_missing(tmp_path):
    """auth/specification/filters not filled — necessary"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
emulator:
  url: "http://localhost:8080"
""")
    config = load_config(str(config_file))
 
    assert config.emulator.timeout == 10
    assert config.auth.type == "basic"
    assert config.specification.version == "1.2.9"
    assert config.filters.resources == []
 