import json
from types import SimpleNamespace

from verifier.reporter import Reporter


def make_config(tmp_path):
    return SimpleNamespace(
        emulator_url="http://localhost:8080",
        output_path=str(tmp_path),
        spec_version="Swordfish v1.2.9",
    )


def test_reporter_builds_summary(tmp_path):
    reporter = Reporter()

    results = [
        {"resource": "ServiceRoot", "status": "PASS"},
        {"resource": "ServiceRoot", "status": "FAIL"},
        {"resource": "Volumes", "status": "NOT_SUPPORTED"},
        {"resource": "Drives", "status": "UNKNOWN"},
    ]

    report = reporter.generate(results, make_config(tmp_path))

    assert report["summary"]["total"] == 4
    assert report["summary"]["pass"] == 1
    assert report["summary"]["fail"] == 1
    assert report["summary"]["not_supported"] == 1
    assert report["summary"]["unknown"] == 1
    assert report["summary"]["pass_rate"] == 25.0


def test_reporter_groups_by_resource(tmp_path):
    reporter = Reporter()

    results = [
        {"resource": "ServiceRoot", "status": "PASS"},
        {"resource": "ServiceRoot", "status": "FAIL"},
        {"resource": "Volumes", "status": "PASS"},
    ]

    report = reporter.generate(results, make_config(tmp_path))

    assert report["resources_checked"] == 2

    assert report["by_resource"]["ServiceRoot"]["pass"] == 1
    assert report["by_resource"]["ServiceRoot"]["fail"] == 1
    assert len(report["by_resource"]["ServiceRoot"]["checks"]) == 2

    assert report["by_resource"]["Volumes"]["pass"] == 1
    assert report["by_resource"]["Volumes"]["fail"] == 0


def test_reporter_extracts_failed_checks(tmp_path):
    reporter = Reporter()

    results = [
        {
            "resource": "ServiceRoot",
            "check": "HTTP статус код",
            "status": "PASS",
        },
        {
            "resource": "StorageSystems",
            "check": "HTTP статус код",
            "status": "FAIL",
            "detail": "Ожидался 200, получен 404",
        },
    ]

    report = reporter.generate(results, make_config(tmp_path))

    assert len(report["failed_checks"]) == 1
    assert len(report["errors"]) == 1
    assert report["failed_checks"][0]["resource"] == "StorageSystems"
    assert report["errors"][0]["status"] == "FAIL"


def test_reporter_saves_json_file(tmp_path):
    reporter = Reporter()

    results = [
        {
            "resource": "ServiceRoot",
            "check": "Поле: Id",
            "status": "PASS",
            "detail": "Поле прошло проверку",
        }
    ]

    report = reporter.generate(results, make_config(tmp_path))

    report_path = tmp_path / "report.json"

    assert report_path.exists()
    assert report["metadata"]["report_path"] == str(report_path)

    with report_path.open("r", encoding="utf-8") as file:
        saved_report = json.load(file)

    assert saved_report["summary"]["total"] == 1
    assert saved_report["summary"]["pass"] == 1
    assert saved_report["all_checks"] == results


def test_reporter_uses_unknown_resource_when_resource_missing(tmp_path):
    reporter = Reporter()

    results = [
        {"status": "PASS"},
    ]

    report = reporter.generate(results, make_config(tmp_path))

    assert report["resources_checked"] == 1
    assert "unknown" in report["by_resource"]
    assert report["by_resource"]["unknown"]["pass"] == 1


def test_reporter_uses_default_output_path_if_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    reporter = Reporter()
    config = SimpleNamespace(
        emulator_url="http://localhost:8080",
        spec_version="Swordfish v1.2.9",
    )

    report = reporter.generate([], config)

    assert report["summary"]["total"] == 0
    assert report["summary"]["pass_rate"] == 0.0
    assert (tmp_path / "reports" / "report.json").exists()
    
