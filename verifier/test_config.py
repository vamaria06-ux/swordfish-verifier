
import pytest
from config import load_config, ConfigError
  
def _write_config(tmp_path, specification_path, extra=""):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(f"""
specification_path: "{specification_path}"
emulator_url: "http://localhost:8080"
timeout: 10
output_path: "./reports"
{extra}
""")
    return config_file
 
 
def test_load_valid_config(tmp_path):
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir()
 
    config_file = _write_config(
        tmp_path, str(schemas_dir),
        extra="""auth:
  type: "basic"
  username: "admin"
  password: "admin"
resources_filter:
  - "Volumes"
"""
    )
    config = load_config(str(config_file))
 
    assert config.specification_path == str(schemas_dir)
    assert config.emulator_url == "http://localhost:8080"
    assert config.timeout == 10
    assert config.output_path == "./reports"
    assert config.auth.username == "admin"
    assert config.resources_filter == ["Volumes"]
 
 
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
    config_file.write_text("""
specification_path: "./specs/schemas"
timeout: 10
""")
    with pytest.raises(ConfigError, match="emulator_url.*output_path|output_path.*emulator_url"):
        load_config(str(config_file))
 
 
def test_optional_fields_can_be_omitted(tmp_path):
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir()
 
    config_file = _write_config(tmp_path, str(schemas_dir))
    config = load_config(str(config_file))
 
    assert config.auth is None
    assert config.resources_filter == []
 
 
def test_specification_path_must_exist(tmp_path):
    """Config Failed: Mandatory filled wrong, file is empty or wrong way to build"""
    config_file = _write_config(tmp_path, str(tmp_path / "нет_такой_папки"))
 
    with pytest.raises(ConfigError, match="way not exist"):
        load_config(str(config_file))
 
 
def test_specification_path_must_be_directory_not_file(tmp_path):
    """specification_path have to have direectory not proper file
    (due to schemas_dir в UniversalSchemaParser.__init__)"""
    fake_file = tmp_path / "specification.json"
    fake_file.write_text("{}")
 
    config_file = _write_config(tmp_path, str(fake_file))
 
    with pytest.raises(ConfigError, match="diryctory"):
        load_config(str(config_file))
 