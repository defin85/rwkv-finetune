import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class BuildDatasetV0ReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.script = self.repo_root / "scripts" / "build_dataset_v0_report.py"

    def test_report_builder_writes_markdown_and_json_summary(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest = root / "manifest.json"
            eval_summary = root / "eval_summary.json"
            output_md = root / "v0-report.md"
            output_json = root / "v0-report.json"

            manifest.write_text(
                json.dumps(
                    {
                        "dataset_name": "unit-dataset",
                        "dataset_version": "v0",
                        "quality_status": "PASS",
                        "quality_reasons": ["quality gates passed"],
                        "source_summary": {
                            "rows_total": 8,
                            "contours": {"core": 6, "extended": 2},
                            "segments": {"coding_general": 5, "onec_bsl": 3},
                            "categories": {
                                "code_generation": 3,
                                "refactoring": 3,
                                "onec_query": 1,
                                "explanation_review": 1,
                            },
                        },
                        "quality_gates": {
                            "invalid_schema_rows": 0,
                            "invalid_ru_prompt_rows": 0,
                            "secret_or_pii_rows": 0,
                            "invalid_bsl_rows": 0,
                            "split_leakage_exact": 0,
                            "split_leakage_near": 0,
                        },
                        "splits": {
                            "train": {"rows_total": 4},
                            "eval_generation": {"rows_total": 2},
                            "eval_refactoring": {"rows_total": 2},
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            eval_summary.write_text(
                json.dumps(
                    {
                        "overall_verdict": "PASS",
                        "domain_eval": {
                            "verdict": "PASS",
                            "score": 0.81,
                            "categories": {
                                "code_generation": {
                                    "verdict": "PASS",
                                    "score": 0.84,
                                    "samples_total": 12,
                                    "failures_total": 1,
                                }
                            },
                        },
                        "retention_eval": {
                            "verdict": "PASS",
                            "score": 0.79,
                            "categories": {
                                "ru_general": {
                                    "verdict": "PASS",
                                    "score": 0.79,
                                    "samples_total": 6,
                                    "failures_total": 0,
                                }
                            },
                        },
                        "hard_cases": [
                            {
                                "suite": "domain_eval",
                                "category": "refactoring",
                                "prompt": "Рефакторни длинную процедуру проведения документа.",
                                "failure_mode": "missed side effects",
                                "action": "add more history-based 1C refactoring samples",
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    "python",
                    str(self.script),
                    "--manifest",
                    str(manifest),
                    "--eval-summary",
                    str(eval_summary),
                    "--output-md",
                    str(output_md),
                    "--output-json",
                    str(output_json),
                ],
                cwd=self.repo_root,
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr + "\n" + result.stdout)
            markdown = output_md.read_text(encoding="utf-8")
            summary = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertIn("# Dataset v0 Report", markdown)
            self.assertIn("refactoring", markdown)
            self.assertEqual(summary["dataset"]["version"], "v0")
            self.assertEqual(summary["evaluation"]["overall_verdict"], "PASS")
            self.assertEqual(summary["backlog"]["hard_cases_total"], 1)
            self.assertEqual(summary["evaluation"]["domain_eval"]["categories"]["code_generation"]["samples_total"], 12)

    def test_report_builder_fails_on_legacy_eval_summary_without_categories(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest = root / "manifest.json"
            eval_summary = root / "eval_summary.json"
            output_md = root / "v0-report.md"
            output_json = root / "v0-report.json"

            manifest.write_text(
                json.dumps(
                    {
                        "dataset_name": "unit-dataset",
                        "dataset_version": "v0",
                        "quality_status": "PASS",
                        "source_summary": {"rows_total": 1},
                        "quality_gates": {},
                        "splits": {"train": {"rows_total": 1}},
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            eval_summary.write_text(
                json.dumps(
                    {
                        "overall_verdict": "PASS",
                        "domain_eval": {"verdict": "PASS"},
                        "retention_eval": {"verdict": "PASS"},
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    "python",
                    str(self.script),
                    "--manifest",
                    str(manifest),
                    "--eval-summary",
                    str(eval_summary),
                    "--output-md",
                    str(output_md),
                    "--output-json",
                    str(output_json),
                ],
                cwd=self.repo_root,
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing_categories", result.stderr)


if __name__ == "__main__":
    unittest.main()
