import pytest
from config import load_config, ConfigError


def _write_config(tmp_path, schemas_dir, extra=""):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        f'schemas_dir: "{schemas_dir}"\n'
        f'emulator_url: "http://localhost:8080"\n'
        f'timeout: 10\n'
        f'output_path: "./reports"\n'
        f'{extra}')
    return config_file


def test_load_valid_config(tmp_path):
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir()
    config_file = _write_config(
        tmp_path,
        str(schemas_dir),
        extra=(
            "auth:\n"
            '  username: "admin"\n'
            '  password: "admin"\n'
            "resources_filter:\n"
            '  - "Volume"\n'),)
    config = load_config(str(config_file))
    assert config.schemas_dir == str(schemas_dir)
    assert config.emulator_url == "http://localhost:8080"
    assert config.timeout == 10
    assert config.output_path == "./reports"
    assert config.auth.username == "admin"
    assert config.auth.password == "admin"
    assert config.resources_filter == ["Volume"]


def test_rules_path_default(tmp_path):
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir()
    config_file = _write_config(tmp_path, str(schemas_dir))
    config = load_config(str(config_file))
    assert config.rules_path == "data/rules.json"


def test_rules_path_custom(tmp_path):
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir()
    config_file = _write_config(tmp_path,
        str(schemas_dir),
        extra='rules_path: "custom/my_rules.json"\n',)
    config = load_config(str(config_file))
    assert config.rules_path == "custom/my_rules.json"


def test_auth_as_dict(tmp_path):
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir()
    config_file = _write_config(
        tmp_path,
        str(schemas_dir),
        extra=(
            "auth:\n"
            '  username: "admin"\n'
            '  password: "secret"\n'),)
    config = load_config(str(config_file))
    assert config.auth_as_dict() == {"username": "admin", "password": "secret"}


def test_auth_as_dict_returns_none_when_no_auth(tmp_path):
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir()
    config_file = _write_config(tmp_path, str(schemas_dir))
    config = load_config(str(config_file))
    assert config.auth_as_dict() is None


def test_missing_file_raises_error():
    with pytest.raises(ConfigError, match="не найден"):
        load_config("несуществующий_файл.yaml")


def test_empty_file_raises_error(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("")
    with pytest.raises(ConfigError, match="пуст"):
        load_config(str(config_file))


def test_missing_required_field_raises_error(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("schemas_dir: './specs'\ntimeout: 10\n")
    with pytest.raises(ConfigError, match="emulator_url|output_path"):
        load_config(str(config_file))


def test_optional_fields_can_be_omitted(tmp_path):
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir()
    config_file = _write_config(tmp_path, str(schemas_dir))
    config = load_config(str(config_file))
    assert config.auth is None
    assert config.auth_as_dict() is None
    assert config.resources_filter == []


def test_schemas_dir_must_exist(tmp_path):
    config_file = _write_config(tmp_path, str(tmp_path / "нет_такой_папки"))
    with pytest.raises(ConfigError, match="несуществующий путь"):
        load_config(str(config_file))


def test_schemas_dir_must_be_directory_not_file(tmp_path):
    fake_file = tmp_path / "schemas.json"
    fake_file.write_text("{}")
    config_file = _write_config(tmp_path, str(fake_file))
    with pytest.raises(ConfigError, match="директорией"):
        load_config(str(config_file))

