import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType


def load_module() -> ModuleType:
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "build_1c_expert_v4_dataset.py"
    spec = importlib.util.spec_from_file_location("build_1c_expert_v4_dataset", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class OneCExpertV4GatesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_validate_sample_format_detects_raw_json_and_missing_eot(self):
        rows = ['{"instruction":"x","output":"y"}']
        stats = self.module.validate_sample_format(rows)
        self.assertEqual(stats["raw_json_objects"], 1)
        self.assertEqual(stats["invalid_missing_eot"], 1)
        self.assertEqual(stats["invalid_missing_headers"], 1)

    def test_validate_sample_format_accepts_formatter_output(self):
        row = self.module.format_sample("test", "answer")
        stats = self.module.validate_sample_format([row])
        self.assertEqual(stats["raw_json_objects"], 0)
        self.assertEqual(stats["invalid_missing_eot"], 0)
        self.assertEqual(stats["invalid_missing_headers"], 0)

    def test_validate_mix_fails_when_outside_tolerance(self):
        counts = {"onec_bsl": 90, "coding_general": 5, "ru_identity": 5}
        mix = {
            "onec_bsl": 0.5,
            "coding_general": 0.3,
            "ru_identity": 0.2,
            "tolerance_pp": 5,
        }
        reasons = self.module.validate_mix(counts, mix)
        self.assertGreaterEqual(len(reasons), 1)
        self.assertTrue(any("mix[onec_bsl]" in reason for reason in reasons))


if __name__ == "__main__":
    unittest.main()
