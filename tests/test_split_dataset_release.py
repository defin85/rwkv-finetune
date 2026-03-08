import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class SplitDatasetReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.script = self.repo_root / "scripts" / "split_dataset_release.py"

    def canonical_row(
        self,
        user_prompt: str,
        assistant_response: str,
        *,
        category: str,
        repo_id: str,
        commit_timestamp: int,
    ) -> dict:
        return {
            "user_prompt": user_prompt,
            "assistant_response": assistant_response,
            "metadata": {
                "source": "unit-test",
                "license": "internal",
                "origin_ref": f"local://{repo_id}",
                "contour": "core",
                "segment": "coding_general",
                "split": "train",
                "category": category,
                "repo_id": repo_id,
                "commit_timestamp": commit_timestamp,
            },
        }

    def write_jsonl(self, path: Path, rows: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def run_splitter(self, workdir: Path, rows: list[dict]) -> subprocess.CompletedProcess[str]:
        input_path = workdir / "input.jsonl"
        self.write_jsonl(input_path, rows)
        command = [
            "python",
            str(self.script),
            "--input",
            str(input_path),
            "--train-output",
            str(workdir / "train.jsonl"),
            "--eval-output",
            str(workdir / "eval.jsonl"),
            "--eval-generation-output",
            str(workdir / "eval_generation.jsonl"),
            "--eval-refactoring-output",
            str(workdir / "eval_refactoring.jsonl"),
            "--manifest-output",
            str(workdir / "manifest.json"),
            "--dataset-name",
            "unit-dataset",
            "--dataset-version",
            "v0",
            "--repo-key",
            "repo_id",
            "--time-key",
            "commit_timestamp",
        ]
        return subprocess.run(command, cwd=self.repo_root, check=False, text=True, capture_output=True)

    def test_splitter_writes_repo_time_release_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            rows = [
                self.canonical_row(
                    "Напиши функцию расчета скидки v1.",
                    "def discount_v1(order):\n    return 0",
                    category="code_generation",
                    repo_id="repo-a",
                    commit_timestamp=100,
                ),
                self.canonical_row(
                    "Рефакторни расчет скидки v1.",
                    "def discount_refactor_v1(order):\n    return bool(order)",
                    category="refactoring",
                    repo_id="repo-a",
                    commit_timestamp=200,
                ),
                self.canonical_row(
                    "Напиши функцию расчета скидки v2.",
                    "def discount_v2(order):\n    return 1",
                    category="code_generation",
                    repo_id="repo-a",
                    commit_timestamp=300,
                ),
                self.canonical_row(
                    "Рефакторни расчет скидки v2.",
                    "def discount_refactor_v2(order):\n    return order is not None",
                    category="refactoring",
                    repo_id="repo-b",
                    commit_timestamp=400,
                ),
                self.canonical_row(
                    "Напиши функцию расчета цены v3.",
                    "def price_v3(order):\n    return 3",
                    category="code_generation",
                    repo_id="repo-b",
                    commit_timestamp=500,
                ),
            ]

            result = self.run_splitter(root, rows)

            self.assertEqual(result.returncode, 0, msg=result.stderr + "\n" + result.stdout)
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["quality_status"], "PASS")
            self.assertEqual(manifest["split_policy"]["strategy"], "repo_temporal_boundary")
            self.assertEqual(manifest["splits"]["train"]["rows_total"], 1)
            self.assertEqual(manifest["splits"]["eval_generation"]["rows_total"], 2)
            self.assertEqual(manifest["splits"]["eval_refactoring"]["rows_total"], 2)

    def test_splitter_fails_closed_without_required_temporal_metadata(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            row = self.canonical_row(
                "Напиши функцию расчета скидки v1.",
                "def discount_v1(order):\n    return 0",
                category="code_generation",
                repo_id="repo-a",
                commit_timestamp=100,
            )
            del row["metadata"]["commit_timestamp"]

            result = self.run_splitter(root, [row])

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing_time_metadata", result.stderr)


if __name__ == "__main__":
    unittest.main()
