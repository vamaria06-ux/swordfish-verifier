import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Reporter:
    """Формирует и сохраняет отчёт по результатам проверки."""

    def generate(self, all_results: list[dict[str, Any]], config) -> dict[str, Any]:
        output_path = self._get_output_path(config)
        by_resource = self._group_by_resource(all_results)
        failed_checks = self._extract_failed_checks(all_results)
        report = {
            "metadata": self._build_metadata(config),
            "summary": self._build_summary(all_results),
            "resources_checked": len(by_resource),
            "failed_checks": failed_checks,
            "errors": failed_checks,
            "by_resource": by_resource,
            "all_checks": all_results,
        }

        report_path = Path(output_path) / "report.json"
        report["metadata"]["report_path"] = str(report_path)
        self._save_json(report, output_path)

        return report

    def _get_output_path(self, config) -> str:
        return getattr(config, "output_path", getattr(config, "output_paht", "reports"))

    def _build_metadata(self, config) -> dict[str, Any]:
        return {
            "version": "1.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "emulator_url": getattr(config, "emulator_url", ""),
            "spec_version": getattr(config, "spec_version", "Swordfish v1.2.9"),
        }

    def _build_summary(self, all_results: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(all_results)
        passed = sum(1 for r in all_results if r.get("status") == "PASS")
        failed = sum(1 for r in all_results if r.get("status") == "FAIL")
        not_supported = sum(1 for r in all_results if r.get("status") == "NOT_SUPPORTED")

        unknown = total - passed - failed - not_supported

        return {
            "total": total,
            "pass": passed,
            "fail": failed,
            "not_supported": not_supported,

            "unknown": unknown,

            "pass_rate": round(passed / total * 100, 2) if total else 0.0,
        }

    def _group_by_resource(
        self,
        all_results: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        by_resource: dict[str, dict[str, Any]] = {}

        for result in all_results:
            resource = result.get("resource") or "unknown"
            status = result.get("status")

            if resource not in by_resource:
                by_resource[resource] = {
                    "pass": 0,
                    "fail": 0,
                    "not_supported": 0,
                    "unknown": 0,
                    "checks": [],
                }

            if status == "PASS":
                by_resource[resource]["pass"] += 1
            elif status == "FAIL":
                by_resource[resource]["fail"] += 1
            elif status == "NOT_SUPPORTED":
                by_resource[resource]["not_supported"] += 1
            else:
                by_resource[resource]["unknown"] += 1

            by_resource[resource]["checks"].append(result)

        return by_resource

    def _extract_failed_checks(
        self,
        all_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [result for result in all_results if result.get("status") == "FAIL"]

    def _save_json(
        self,
        report: dict[str, Any],
        output_path: str,
        filename: str = "report.json",
    ) -> Path:
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        report_path = output_dir / filename

        with report_path.open("w", encoding="utf-8") as file:
            json.dump(report, file, indent=2, ensure_ascii=False, default=str)

        return report_path