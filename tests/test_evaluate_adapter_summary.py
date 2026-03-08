import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class EvaluateAdapterSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.script = self.repo_root / "scripts" / "evaluate_adapter.sh"

    def test_evaluate_adapter_writes_category_summaries_and_hard_cases(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_name = "unit-eval-summary"
            run_dir = self.repo_root / "runs" / run_name
            run_dir.mkdir(parents=True, exist_ok=True)
            output = root / "eval_summary.json"
            domain_categories = root / "domain_categories.json"
            retention_categories = root / "retention_categories.json"
            hard_cases = root / "hard_cases.json"

            domain_categories.write_text(
                json.dumps(
                    {
                        "code_generation": {
                            "verdict": "PASS",
                            "score": 0.84,
                            "samples_total": 12,
                            "failures_total": 1,
                        },
                        "refactoring": {
                            "verdict": "FAIL",
                            "score": 0.55,
                            "samples_total": 5,
                            "failures_total": 2,
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            retention_categories.write_text(
                json.dumps(
                    {
                        "ru_general": {
                            "verdict": "PASS",
                            "score": 0.79,
                            "samples_total": 6,
                            "failures_total": 0,
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            hard_cases.write_text(
                json.dumps(
                    [
                        {
                            "suite": "domain_eval",
                            "category": "refactoring",
                            "prompt": "Рефакторни длинную процедуру проведения документа.",
                            "failure_mode": "missed side effects",
                            "action": "add more history-based 1C refactoring samples",
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    str(self.script),
                    "--run-name",
                    run_name,
                    "--domain-verdict",
                    "FAIL",
                    "--retention-verdict",
                    "PASS",
                    "--domain-categories",
                    str(domain_categories),
                    "--retention-categories",
                    str(retention_categories),
                    "--hard-cases",
                    str(hard_cases),
                    "--output",
                    str(output),
                ],
                cwd=self.repo_root,
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr + "\n" + result.stdout)
            summary = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(summary["overall_verdict"], "FAIL")
            self.assertEqual(summary["domain_eval"]["categories"]["code_generation"]["samples_total"], 12)
            self.assertEqual(summary["hard_cases"][0]["suite"], "domain_eval")


if __name__ == "__main__":
    unittest.main()
