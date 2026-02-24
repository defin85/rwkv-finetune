import importlib.util
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace


def load_module() -> ModuleType:
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "check_dataset_quality.py"
    spec = importlib.util.spec_from_file_location("check_dataset_quality", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DatasetQualityRulesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def make_args(self):
        return SimpleNamespace(
            min_rows=1,
            min_unique_ratio=0.0,
            min_user_assistant_ratio=1.0,
            min_identity_ratio=0.0,
            max_top1_share=1.0,
            max_qwen_negative_rows=0,
            max_identity_brand_leak_rows=0,
            max_transcript_leak_rows=0,
        )

    def test_transcript_leakage_fails_quality(self):
        rows = [
            "User: кто ты?\nAssistant: Я RWKV-7. User: кто ты? Assistant: Я RWKV-7.",
        ]
        report = self.module.evaluate(rows, self.make_args())
        self.assertEqual(report["quality_status"], "FAIL")
        self.assertIn("transcript_leak_rows=1 > max_transcript_leak_rows=0", report["quality_reasons"])
        self.assertEqual(report["metrics"]["transcript_leak_rows"], 1)

    def test_identity_brand_leakage_fails_quality(self):
        rows = [
            "User: кто ты?\nAssistant: Я ChatGPT от OpenAI.",
        ]
        report = self.module.evaluate(rows, self.make_args())
        self.assertEqual(report["quality_status"], "FAIL")
        self.assertIn(
            "identity_brand_leak_rows=1 > max_identity_brand_leak_rows=0",
            report["quality_reasons"],
        )
        self.assertEqual(report["metrics"]["identity_brand_leak_rows"], 1)

    def test_clean_identity_row_passes(self):
        rows = [
            "User: кто ты?\nAssistant: В этом чате используется модель RWKV-7.",
        ]
        report = self.module.evaluate(rows, self.make_args())
        self.assertEqual(report["quality_status"], "PASS")
        self.assertEqual(report["metrics"]["transcript_leak_rows"], 0)
        self.assertEqual(report["metrics"]["identity_brand_leak_rows"], 0)


if __name__ == "__main__":
    unittest.main()
