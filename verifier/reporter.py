import json
import os
from datetime import datetime


class Reporter:

    def generate(self, all_results, config):
        total = len(all_results)
        passed = sum(1 for r in all_results if r["status"] == "PASS")
        failed = sum(1 for r in all_results if r["status"] == "FAIL")
        not_supported = sum(1 for r in all_results if r["status"] == "NOT_SUPPORTED")

        # Группируем результаты по ресурсам
        by_resource = {}
        for r in all_results:
            res = r["resource"]
            if res not in by_resource:
                by_resource[res] = {"pass": 0, "fail": 0, "checks": []}
            if r["status"] == "PASS":
                by_resource[res]["pass"] += 1
            elif r["status"] == "FAIL":
                by_resource[res]["fail"] += 1
            by_resource[res]["checks"].append(r)

        report = {
            "metadata": {
                "version": "1.0",
                "timestamp": datetime.now().isoformat(),
                "emulator_url": config.emulator_url,
                "spec_version": "Swordfish v1.2.9"
            },
            "summary": {
                "total": total,
                "pass": passed,
                "fail": failed,
                "not_supported": not_supported,
                "pass_rate": f"{round(passed/total*100)}%" if total > 0 else "0%"
            },
            "by_resource": by_resource,
            "all_checks": all_results
        }

        os.makedirs(config.output_path, exist_ok=True)
        path = os.path.join(config.output_path, "report.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        return report
