import json

from verifier.parser import Parser, UniversalSchemaParser, adapt_rules


BUILTIN_RESOURCES = [
    "ServiceRoot", "Systems", "StorageSystems",
    "StoragePools", "Volumes", "Drives",
]


# ---------- Parser: встроенные правила ----------

def test_builtin_rules_cover_all_resources():
    rules = Parser().load_rules()
    for resource in BUILTIN_RESOURCES:
        assert resource in rules


def test_builtin_rules_have_endpoint_and_required_fields():
    rules = Parser().load_rules()
    for resource, rule in rules.items():
        assert "endpoint" in rule
        assert rule["required_fields"]


def test_resources_filter_limits_builtin_rules():
    rules = Parser().load_rules(resources_filter=["ServiceRoot", "Systems"])
    assert set(rules.keys()) == {"ServiceRoot", "Systems"}


def test_resources_filter_none_returns_all_resources():
    rules = Parser().load_rules(resources_filter=None)
    assert set(rules.keys()) == set(BUILTIN_RESOURCES)


def test_resources_filter_unknown_resource_returns_empty():
    rules = Parser().load_rules(resources_filter=["NoSuchResource"])
    assert rules == {}


# ---------- Parser: save/load правил ----------

def test_save_and_load_rules_roundtrip(tmp_path):
    parser = Parser()
    rules = parser.load_rules(resources_filter=["ServiceRoot"])
    output_path = tmp_path / "rules.json"

    parser.save_rules(rules, str(output_path))
    loaded = parser.load_rules(rules_path=str(output_path))

    assert loaded == rules


def test_load_rules_missing_rules_path_falls_back_to_builtin(tmp_path):
    missing_path = tmp_path / "does_not_exist.json"
    rules = Parser().load_rules(rules_path=str(missing_path))
    assert set(rules.keys()) == set(BUILTIN_RESOURCES)


# ---------- UniversalSchemaParser: вспомогательные методы ----------

def test_get_resource_name_extracts_base_name():
    parser = UniversalSchemaParser(schemas_dir="unused")
    assert parser.get_resource_name("Volume.v1_11_0.json") == "Volume"


def test_get_resource_name_fallback_without_version():
    parser = UniversalSchemaParser(schemas_dir="unused")
    assert parser.get_resource_name("SomeFile.json") == "SomeFile"


def test_get_latest_file_picks_highest_version():
    parser = UniversalSchemaParser(schemas_dir="unused")
    files = ["Volume.v1_2_0.json", "Volume.v1_11_0.json", "Volume.v1_9_0.json"]
    assert parser.get_latest_file(files, "Volume") == "Volume.v1_11_0.json"


def test_get_latest_file_ignores_zone_identifier_files():
    parser = UniversalSchemaParser(schemas_dir="unused")
    files = [
        "Volume.v1_9_0.json",
        "Volume.v1_11_0.json:Zone.Identifier",
    ]
    assert parser.get_latest_file(files, "Volume") == "Volume.v1_9_0.json"


def test_get_latest_file_returns_none_without_matching_files():
    parser = UniversalSchemaParser(schemas_dir="unused")
    assert parser.get_latest_file([], "Volume") is None


# ---------- UniversalSchemaParser: extract_definition ----------

def test_extract_definition_finds_by_resource_name():
    parser = UniversalSchemaParser(schemas_dir="unused")
    schema = {
        "definitions": {
            "Volume": {"properties": {"Id": {"type": "string"}}},
            "Actions": {"properties": {}},
        }
    }
    definition = parser.extract_definition(schema, "Volume")
    assert definition == schema["definitions"]["Volume"]


def test_extract_definition_falls_back_to_single_definition():
    parser = UniversalSchemaParser(schemas_dir="unused")
    schema = {"definitions": {"OnlyOne": {"properties": {}}}}
    definition = parser.extract_definition(schema, "Volume")
    assert definition == schema["definitions"]["OnlyOne"]


def test_extract_definition_returns_empty_when_ambiguous():
    parser = UniversalSchemaParser(schemas_dir="unused")
    schema = {"definitions": {"A": {}, "B": {}}}
    assert parser.extract_definition(schema, "Volume") == {}


# ---------- UniversalSchemaParser: extract_field_info ----------

def test_extract_field_info_resolves_ref_type():
    parser = UniversalSchemaParser(schemas_dir="unused")
    definitions = {"Status": {"type": "object"}}
    field_details = {"$ref": "#/definitions/Status"}
    info = parser.extract_field_info("Status", field_details, definitions)
    assert info["type"] == "object"
    assert info["$ref"] == "#/definitions/Status"


def test_extract_field_info_array_of_objects():
    parser = UniversalSchemaParser(schemas_dir="unused")
    field_details = {
        "type": "array",
        "items": {"$ref": "#/definitions/Drive"},
    }
    info = parser.extract_field_info("Drives", field_details, {})
    assert info["items_type"] == "object"


def test_extract_field_info_array_of_primitives():
    parser = UniversalSchemaParser(schemas_dir="unused")
    field_details = {"type": "array", "items": {"type": "string"}}
    info = parser.extract_field_info("Tags", field_details, {})
    assert info["items_type"] == "string"


# ---------- UniversalSchemaParser: parse_resource / parse_all ----------

def _write_minimal_schema(tmp_path, filename, resource_name):
    schema = {
        "release": "1.0.0",
        "definitions": {
            resource_name: {
                "required": ["Id", "Name"],
                "properties": {
                    "Id": {"type": "string", "description": "Идентификатор"},
                    "Name": {"type": "string", "description": "Имя"},
                    "State": {
                        "type": "string",
                        "enum": ["Enabled", "Disabled"],
                    },
                },
            },
            "State": {"enum": ["Enabled", "Disabled"]},
        },
    }
    filepath = tmp_path / filename
    filepath.write_text(json.dumps(schema), encoding="utf-8")
    return str(filepath)


def test_parse_resource_end_to_end(tmp_path):
    filepath = _write_minimal_schema(tmp_path, "Volume.v1_0_0.json", "Volume")
    parser = UniversalSchemaParser(schemas_dir=str(tmp_path))

    result = parser.parse_resource(filepath)

    assert result["resource"] == "Volume"
    assert result["version"] == "1.0.0"
    assert set(result["required_fields"]) == {"Id", "Name"}
    assert "Id" in result["fields"]
    assert "State" in result["enums"]


def test_parse_resource_missing_file_returns_none(tmp_path):
    parser = UniversalSchemaParser(schemas_dir=str(tmp_path))
    result = parser.parse_resource(str(tmp_path / "no_such_file.json"))
    assert result is None


def test_parse_all_filters_and_parses_resources(tmp_path):
    _write_minimal_schema(tmp_path, "Volume.v1_0_0.json", "Volume")
    _write_minimal_schema(tmp_path, "Drive.v1_0_0.json", "Drive")

    parser = UniversalSchemaParser(schemas_dir=str(tmp_path))
    rules = parser.parse_all(resources_filter=["Volume"])

    assert set(rules.keys()) == {"Volume"}


# ---------- adapt_rules ----------

def test_adapt_rules_keeps_known_type():
    grgit_rules = {
        "Volume": {
            "version": "1.0.0",
            "required_fields": ["Id"],
            "fields": {
                "Id": {"type": "string", "description": "Идентификатор"},
            },
        }
    }
    adapted = adapt_rules(grgit_rules)
    assert adapted["Volume"]["required_fields"]["Id"]["type"] == "str"


def test_adapt_rules_marks_unknown_type_as_none():
    grgit_rules = {
        "Volume": {
            "version": "1.0.0",
            "required_fields": ["Status"],
            "fields": {
                "Status": {"type": "unknown", "description": "Статус"},
            },
        }
    }
    adapted = adapt_rules(grgit_rules)
    assert adapted["Volume"]["required_fields"]["Status"]["type"] is None


def test_adapt_rules_builds_endpoint_from_mapping():
    grgit_rules = {
        "ComputerSystem": {
            "version": "1.0.0",
            "required_fields": [],
            "fields": {},
        }
    }
    adapted = adapt_rules(grgit_rules)
    assert adapted["ComputerSystem"]["endpoint"] == "/redfish/v1/Systems"
    assert adapted["ComputerSystem"]["dynamic"] is False


def test_adapt_rules_unknown_resource_gets_generated_endpoint():
    grgit_rules = {
        "Chassis": {
            "version": "1.0.0",
            "required_fields": [],
            "fields": {},
        }
    }
    adapted = adapt_rules(grgit_rules)
    assert adapted["Chassis"]["endpoint"] == "/redfish/v1/Chassiss"


# ---------- Parser: загрузка из файлов схем ----------

def test_load_rules_from_spec_path_merges_with_builtin(tmp_path):
    _write_minimal_schema(tmp_path, "Volume.v1_0_0.json", "Volume")

    rules = Parser().load_rules(spec_path=str(tmp_path))

    assert "Volume" in rules
    assert rules["Volume"]["required_fields"]["Id"]["type"] == "str"
    # ServiceRoot не пришёл из файлов схем -> взят из встроенных правил
    assert "ServiceRoot" in rules


def test_load_rules_from_empty_spec_path_falls_back_to_builtin(tmp_path):
    rules = Parser().load_rules(spec_path=str(tmp_path))
    assert set(rules.keys()) == set(BUILTIN_RESOURCES)
