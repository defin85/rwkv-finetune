import json
import unittest
from pathlib import Path


class OneCExpertV4ProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path = (
            Path(__file__).resolve().parents[1]
            / "configs"
            / "dataset"
            / "1c-expert-v4.profile.json"
        )

    def test_profile_exists_and_has_required_contract(self):
        self.assertTrue(self.path.is_file(), f"profile file is missing: {self.path}")
        payload = json.loads(self.path.read_text(encoding="utf-8"))

        self.assertEqual(payload["profile_id"], "1c-expert-v4")
        self.assertEqual(payload["version"], 1)

        volume = payload["volume"]
        self.assertEqual(volume["target_min_mb"], 500)
        self.assertEqual(volume["target_max_mb"], 1024)
        self.assertEqual(volume["hard_min_mb"], 200)

        mix = payload["mix"]
        self.assertEqual(mix["onec_bsl"], 0.5)
        self.assertEqual(mix["coding_general"], 0.3)
        self.assertEqual(mix["ru_identity"], 0.2)
        self.assertEqual(mix["tolerance_pp"], 5)

        gates = payload["release_gates"]
        self.assertTrue(gates["require_shuffle"])
        self.assertTrue(gates["forbid_raw_json_objects_in_train_text"])
        self.assertTrue(gates["require_eot_per_sample"])

    def test_allowlist_has_required_sources_and_provenance_fields(self):
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        allowlist = payload["source_allowlist"]
        expected_ids = {
            "ise-uiuc/MagicCoder-Evol-Instruct-110K",
            "sahil2801/CodeAlpaca-20k",
            "IlyaGusev/saiga_scored",
            "IlyaGusev/ru_turbo_alpaca",
        }
        self.assertEqual({item["dataset_id"] for item in allowlist}, expected_ids)

        required = set(payload["required_provenance_fields"])
        self.assertEqual(
            required,
            {"source", "license", "origin_ref", "segment"},
        )
        for item in allowlist:
            self.assertIn(item["segment"], {"coding_general", "ru_identity"})
            self.assertIsInstance(item["license"], str)


if __name__ == "__main__":
    unittest.main()
