import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class ValidateDatasetReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.script = self.repo_root / "scripts" / "validate_dataset_release.py"

    def write_jsonl(self, path: Path, rows: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def canonical_row(
        self,
        user_prompt: str,
        assistant_response: str,
        split: str,
        category: str,
        contour: str = "extended",
        segment: str = "coding_general",
    ) -> dict:
        return {
            "user_prompt": user_prompt,
            "assistant_response": assistant_response,
            "metadata": {
                "source": "unit-test",
                "license": "internal",
                "origin_ref": "local://unit",
                "contour": contour,
                "segment": segment,
                "split": split,
                "category": category,
            },
        }

    def run_validator(
        self,
        workdir: Path,
        train_rows: list[dict],
        eval_rows: list[dict],
        enforce_balance: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        train = workdir / "train.jsonl"
        eval_path = workdir / "eval.jsonl"
        manifest = workdir / "manifest.json"
        self.write_jsonl(train, train_rows)
        self.write_jsonl(eval_path, eval_rows)
        command = [
            "python",
            str(self.script),
            "--train",
            str(train),
            "--eval",
            str(eval_path),
            "--manifest-output",
            str(manifest),
            "--dataset-name",
            "unit-dataset",
            "--dataset-version",
            "v0",
        ]
        if enforce_balance:
            command.append("--enforce-balance")
        return subprocess.run(command, cwd=self.repo_root, text=True, capture_output=True, check=False)

    def test_validator_writes_manifest_for_clean_release(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            result = self.run_validator(
                root,
                train_rows=[
                    self.canonical_row(
                        user_prompt="Напиши функцию обработки заказа.",
                        assistant_response="def handle_order(order):\n    return bool(order)",
                        split="train",
                        category="code_generation",
                    ),
                    self.canonical_row(
                        user_prompt="Рефакторни функцию обработки заказа.",
                        assistant_response="def handle_order(order):\n    return order is not None",
                        split="train",
                        category="refactoring",
                    ),
                ],
                eval_rows=[
                    self.canonical_row(
                        user_prompt="Рефакторни функцию проверки оплаты.",
                        assistant_response="def is_paid(order):\n    return order.status == 'paid'",
                        split="eval",
                        category="refactoring",
                    )
                ],
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr + "\n" + result.stdout)
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["quality_status"], "PASS")
            self.assertEqual(manifest["dataset_version"], "v0")
            self.assertIn("splits", manifest)
            self.assertEqual(manifest["splits"]["train"]["rows_total"], 2)

    def test_validator_fails_on_cross_split_leakage(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            leaked = self.canonical_row(
                user_prompt="Напиши функцию обработки заказа.",
                assistant_response="def handle_order(order):\n    return bool(order)",
                split="train",
                category="code_generation",
            )
            result = self.run_validator(root, train_rows=[leaked], eval_rows=[dict(leaked, metadata={**leaked["metadata"], "split": "eval"})])
            self.assertNotEqual(result.returncode, 0)
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["quality_status"], "FAIL")
            self.assertTrue(any("split_leakage_exact" in reason for reason in manifest["quality_reasons"]))

    def test_validator_fails_on_secret_or_pii(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            result = self.run_validator(
                root,
                train_rows=[
                    self.canonical_row(
                        user_prompt="Напиши код для обработки email клиента.",
                        assistant_response="Почта клиента: ivan.petrov@example.com",
                        split="train",
                        category="code_generation",
                    )
                ],
                eval_rows=[
                    self.canonical_row(
                        user_prompt="Рефакторни обработчик заказа.",
                        assistant_response="def handle(order):\n    return order is not None",
                        split="eval",
                        category="refactoring",
                    )
                ],
            )
            self.assertNotEqual(result.returncode, 0)
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(any("secret_or_pii_rows" in reason for reason in manifest["quality_reasons"]))

