import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class NormalizeDatasetJsonlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.script = self.repo_root / "scripts" / "normalize_dataset_jsonl.py"

    def write_rows(self, path: Path, rows: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def run_script(self, input_path: Path, output_path: Path) -> subprocess.CompletedProcess[str]:
        command = [
            "python",
            str(self.script),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--contour",
            "extended",
            "--segment",
            "coding_general",
            "--source",
            "unit-test",
            "--license",
            "internal",
            "--origin-ref",
            "local://unit",
            "--split",
            "train",
        ]
        return subprocess.run(command, cwd=self.repo_root, text=True, capture_output=True, check=False)

    def test_normalizer_converts_legacy_instruction_output_rows(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            input_path = root / "legacy.jsonl"
            output_path = root / "canonical.jsonl"
            self.write_rows(
                input_path,
                [
                    {"instruction": "Напиши функцию.", "output": "def f():\n    return 1"},
                ],
            )
            result = self.run_script(input_path, output_path)
            self.assertEqual(result.returncode, 0, msg=result.stderr + "\n" + result.stdout)
            rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["metadata"]["contour"], "extended")
            self.assertEqual(rows[0]["metadata"]["source"], "unit-test")
            self.assertIn("User:", rows[0]["text"])
            self.assertIn("Assistant:", rows[0]["text"])

    def test_normalizer_fails_closed_on_non_russian_prompt(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            input_path = root / "legacy.jsonl"
            output_path = root / "canonical.jsonl"
            self.write_rows(
                input_path,
                [
                    {"instruction": "Write a Python function.", "output": "def f():\n    return 1"},
                ],
            )
            result = self.run_script(input_path, output_path)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output_path.exists())
            self.assertIn("user_prompt_not_russian", result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
