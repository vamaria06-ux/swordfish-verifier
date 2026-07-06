import pytest
from verifier.config import load_config, ConfigError


def _write_config(tmp_path, content):
    config_file = tmp_path / "config.yml"
    config_file.write_text(content, encoding="utf-8")
    return config_file


def test_load_valid_config_minimal(tmp_path):
    """Минимальный конфиг без auth и specification_path загружается"""
    f = _write_config(tmp_path, """
emulator_url: "http://localhost:8080"
timeout: 10
output_path: "./reports"
""")
    config = load_config(str(f))
    assert config.emulator_url == "http://localhost:8080"
    assert config.timeout == 10
    assert config.output_path == "./reports"
    assert config.auth is None
    assert config.specification_path is None
    assert config.resources_filter == []


def test_load_valid_config_with_auth(tmp_path):
    """Конфиг с auth загружается и auth доступен как dataclass"""
    f = _write_config(tmp_path, """
emulator_url: "http://localhost:8080"
timeout: 10
output_path: "./reports"
auth:
  type: "basic"
  username: "Administrator"
  password: "Password"
""")
    config = load_config(str(f))
    assert config.auth.username == "Administrator"
    assert config.auth.password == "Password"
    assert config.auth.type == "basic"


def test_load_valid_config_with_spec_path(tmp_path):
    """Конфиг с существующим specification_path загружается"""
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir()
    f = _write_config(tmp_path, f"""
emulator_url: "http://localhost:8080"
timeout: 10
output_path: "./reports"
specification_path: "{schemas_dir}"
""")
    config = load_config(str(f))
    assert config.specification_path == str(schemas_dir)


def test_missing_file_raises_error():
    """Файл не существует → ConfigError"""
    with pytest.raises(ConfigError, match="не найден"):
        load_config("несуществующий_файл.yml")


def test_empty_file_raises_error(tmp_path):
    """Пустой файл → ConfigError"""
    f = _write_config(tmp_path, "")
    with pytest.raises(ConfigError, match="пуст"):
        load_config(str(f))


def test_missing_required_field_raises_error(tmp_path):
    """Нет emulator_url → ConfigError"""
    f = _write_config(tmp_path, """
timeout: 10
output_path: "./reports"
""")
    with pytest.raises(ConfigError, match="emulator_url"):
        load_config(str(f))


def test_specification_path_not_exist_raises_error(tmp_path):
    """specification_path указывает на несуществующую папку → ConfigError"""
    f = _write_config(tmp_path, """
emulator_url: "http://localhost:8080"
timeout: 10
output_path: "./reports"
specification_path: "/нет/такой/папки"
""")
    with pytest.raises(ConfigError, match="несуществующий путь"):
        load_config(str(f))


def test_specification_path_file_not_dir_raises_error(tmp_path):
    """specification_path указывает на файл а не папку → ConfigError"""
    fake_file = tmp_path / "schema.json"
    fake_file.write_text("{}")
    f = _write_config(tmp_path, f"""
emulator_url: "http://localhost:8080"
timeout: 10
output_path: "./reports"
specification_path: "{fake_file}"
""")
    with pytest.raises(ConfigError, match="директорией"):
        load_config(str(f))


def test_resources_filter_loaded(tmp_path):
    """resources_filter загружается как список"""
    f = _write_config(tmp_path, """
emulator_url: "http://localhost:8080"
timeout: 10
output_path: "./reports"
resources_filter:
  - "StorageSystems"
  - "Volumes"
""")
    config = load_config(str(f))
    assert config.resources_filter == ["StorageSystems", "Volumes"]
