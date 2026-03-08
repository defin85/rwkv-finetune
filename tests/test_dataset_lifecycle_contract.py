import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import ModuleType


def load_module() -> ModuleType:
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "dataset_lifecycle.py"
    spec = importlib.util.spec_from_file_location("dataset_lifecycle", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DatasetLifecycleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_build_canonical_row_renders_compatibility_text(self):
        row = self.module.build_canonical_row(
            user_prompt="Напиши функцию на Python.",
            assistant_response="def f():\n    return 1",
            metadata={
                "source": "unit-test",
                "license": "internal",
                "origin_ref": "local://unit",
                "contour": "extended",
                "segment": "coding_general",
                "split": "train",
            },
        )
        self.assertEqual(row["user_prompt"], "Напиши функцию на Python.")
        self.assertIn("User:", row["text"])
        self.assertIn("Assistant:", row["text"])
        self.assertEqual(row["metadata"]["source"], "unit-test")

    def test_validate_canonical_row_rejects_non_russian_prompt(self):
        row = self.module.build_canonical_row(
            user_prompt="Write a Python function.",
            assistant_response="def f():\n    return 1",
            metadata={
                "source": "unit-test",
                "license": "internal",
                "origin_ref": "local://unit",
                "contour": "extended",
                "segment": "coding_general",
                "split": "train",
            },
        )
        reasons = self.module.validate_canonical_row(row)
        self.assertTrue(any("user_prompt_not_russian" in reason for reason in reasons))

    def test_validate_canonical_row_rejects_invalid_contour_and_unknown_provenance(self):
        row = self.module.build_canonical_row(
            user_prompt="Напиши функцию на Python.",
            assistant_response="def f():\n    return 1",
            metadata={
                "source": "unknown",
                "license": "unknown",
                "origin_ref": "unknown",
                "contour": "mixed",
                "segment": "coding_general",
                "split": "train",
            },
        )
        reasons = self.module.validate_canonical_row(row)
        self.assertTrue(any("invalid_metadata.contour" in reason for reason in reasons))
        self.assertTrue(any("invalid_metadata.source" in reason for reason in reasons))
        self.assertTrue(any("invalid_metadata.license" in reason for reason in reasons))
        self.assertTrue(any("invalid_metadata.origin_ref" in reason for reason in reasons))

    def test_validate_category_balance_flags_out_of_range_release(self):
        rows = [
            self.module.build_canonical_row(
                user_prompt=f"Напиши код {index}",
                assistant_response="print(1)",
                metadata={
                    "source": "unit-test",
                    "license": "internal",
                    "origin_ref": "local://unit",
                    "contour": "extended",
                    "segment": "coding_general",
                    "split": "train",
                    "category": "code_generation",
                },
            )
            for index in range(9)
        ]
        rows.append(
            self.module.build_canonical_row(
                user_prompt="Объясни код кратко.",
                assistant_response="Это простой пример.",
                metadata={
                    "source": "unit-test",
                    "license": "internal",
                    "origin_ref": "local://unit",
                    "contour": "extended",
                    "segment": "coding_general",
                    "split": "train",
                    "category": "explanation_review",
                },
            )
        )
        counts = self.module.category_distribution(rows)
        reasons = self.module.validate_category_balance(counts)
        self.assertTrue(any("category_balance[code_generation]" in reason for reason in reasons))

    def test_build_release_manifest_contains_required_strategy_sections(self):
        train_rows = [
            self.module.build_canonical_row(
                user_prompt="Напиши функцию для обработки заказа.",
                assistant_response="def handle_order():\n    return True",
                metadata={
                    "source": "unit-test",
                    "license": "internal",
                    "origin_ref": "local://unit",
                    "contour": "core",
                    "segment": "coding_general",
                    "split": "train",
                    "category": "code_generation",
                },
            )
        ]
        eval_rows = [
            self.module.build_canonical_row(
                user_prompt="Рефакторни функцию обработки заказа.",
                assistant_response="def handle_order(order):\n    return bool(order)",
                metadata={
                    "source": "unit-test",
                    "license": "internal",
                    "origin_ref": "local://unit",
                    "contour": "core",
                    "segment": "coding_general",
                    "split": "eval",
                    "category": "refactoring",
                },
            )
        ]
        manifest = self.module.build_release_manifest(
            dataset_name="unit-dataset",
            dataset_version="v0",
            created_by="tests/test_dataset_lifecycle_contract.py",
            rows_by_split={"train": train_rows, "eval": eval_rows},
            split_artifacts={
                "train": {"path": "/tmp/train.jsonl", "sha256": "abc", "rows_total": 1},
                "eval": {"path": "/tmp/eval.jsonl", "sha256": "def", "rows_total": 1},
            },
            enforce_balance=False,
            required_eval_categories=("refactoring",),
        )
        self.assertEqual(manifest["dataset_version"], "v0")
        self.assertIn("source_summary", manifest)
        self.assertIn("license_summary", manifest)
        self.assertIn("sampling_policy", manifest)
        self.assertIn("dedup_policy", manifest)
        self.assertIn("split_policy", manifest)
        self.assertIn("storage_layout", manifest)
        self.assertIn("quality_status", manifest)
        self.assertEqual(manifest["splits"]["train"]["rows_total"], 1)
        self.assertEqual(manifest["splits"]["eval"]["rows_total"], 1)

    def test_split_rows_by_repo_time_creates_dedicated_eval_buckets(self):
        rows = [
            self.module.build_canonical_row(
                user_prompt="Напиши функцию расчета скидки v1.",
                assistant_response="def discount_v1(order):\n    return 0",
                metadata={
                    "source": "unit-test",
                    "license": "internal",
                    "origin_ref": "local://repo-a",
                    "contour": "core",
                    "segment": "coding_general",
                    "split": "train",
                    "category": "code_generation",
                    "repo_id": "repo-a",
                    "commit_timestamp": 100,
                },
            ),
            self.module.build_canonical_row(
                user_prompt="Рефакторни расчет скидки v1.",
                assistant_response="def discount_refactor_v1(order):\n    return bool(order)",
                metadata={
                    "source": "unit-test",
                    "license": "internal",
                    "origin_ref": "local://repo-a",
                    "contour": "core",
                    "segment": "coding_general",
                    "split": "train",
                    "category": "refactoring",
                    "repo_id": "repo-a",
                    "commit_timestamp": 200,
                },
            ),
            self.module.build_canonical_row(
                user_prompt="Напиши функцию расчета скидки v2.",
                assistant_response="def discount_v2(order):\n    return 1",
                metadata={
                    "source": "unit-test",
                    "license": "internal",
                    "origin_ref": "local://repo-a",
                    "contour": "core",
                    "segment": "coding_general",
                    "split": "train",
                    "category": "code_generation",
                    "repo_id": "repo-a",
                    "commit_timestamp": 300,
                },
            ),
            self.module.build_canonical_row(
                user_prompt="Рефакторни расчет скидки v2.",
                assistant_response="def discount_refactor_v2(order):\n    return order is not None",
                metadata={
                    "source": "unit-test",
                    "license": "internal",
                    "origin_ref": "local://repo-b",
                    "contour": "core",
                    "segment": "coding_general",
                    "split": "train",
                    "category": "refactoring",
                    "repo_id": "repo-b",
                    "commit_timestamp": 400,
                },
            ),
            self.module.build_canonical_row(
                user_prompt="Напиши функцию расчета цены v3.",
                assistant_response="def price_v3(order):\n    return 3",
                metadata={
                    "source": "unit-test",
                    "license": "internal",
                    "origin_ref": "local://repo-b",
                    "contour": "core",
                    "segment": "coding_general",
                    "split": "train",
                    "category": "code_generation",
                    "repo_id": "repo-b",
                    "commit_timestamp": 500,
                },
            ),
        ]
        rows_by_split, report = self.module.split_rows_by_repo_time(
            rows,
            repo_keys=("repo_id",),
            time_keys=("commit_timestamp",),
            eval_split_categories={
                "eval_generation": "code_generation",
                "eval_refactoring": "refactoring",
            },
        )
        self.assertEqual(len(rows_by_split["eval_generation"]), 2)
        self.assertEqual(len(rows_by_split["eval_refactoring"]), 2)
        self.assertEqual(len(rows_by_split["eval"]), 4)
        self.assertEqual(len(rows_by_split["train"]), 1)
        self.assertEqual(
            {row["metadata"]["category"] for row in rows_by_split["eval_generation"]},
            {"code_generation"},
        )
        self.assertEqual(
            {row["metadata"]["category"] for row in rows_by_split["eval_refactoring"]},
            {"refactoring"},
        )
        self.assertEqual(report["resolved_repo_keys"], {"repo_id": 5})
        self.assertEqual(report["resolved_time_keys"], {"commit_timestamp": 5})

    def test_build_release_manifest_flags_invalid_dedicated_eval_split(self):
        train_rows = [
            self.module.build_canonical_row(
                user_prompt="Напиши функцию обработки заказа.",
                assistant_response="def handle_order():\n    return True",
                metadata={
                    "source": "unit-test",
                    "license": "internal",
                    "origin_ref": "local://unit",
                    "contour": "core",
                    "segment": "coding_general",
                    "split": "train",
                    "category": "code_generation",
                },
            )
        ]
        eval_generation = [
            self.module.build_canonical_row(
                user_prompt="Рефакторни функцию обработки заказа.",
                assistant_response="def handle_order(order):\n    return bool(order)",
                metadata={
                    "source": "unit-test",
                    "license": "internal",
                    "origin_ref": "local://unit",
                    "contour": "core",
                    "segment": "coding_general",
                    "split": "eval_generation",
                    "category": "refactoring",
                },
            )
        ]
        manifest = self.module.build_release_manifest(
            dataset_name="unit-dataset",
            dataset_version="v0",
            created_by="tests/test_dataset_lifecycle_contract.py",
            rows_by_split={"train": train_rows, "eval_generation": eval_generation},
            split_artifacts={
                "train": {"path": "/tmp/train.jsonl", "sha256": "abc", "rows_total": 1},
                "eval_generation": {"path": "/tmp/eval_generation.jsonl", "sha256": "def", "rows_total": 1},
            },
            enforce_balance=False,
            eval_split_categories={"eval_generation": "code_generation"},
        )
        self.assertEqual(manifest["quality_status"], "FAIL")
        self.assertTrue(
            any("invalid_eval_split_category[eval_generation]" in reason for reason in manifest["quality_reasons"])
        )

    def test_policy_file_matches_expected_stage_layout(self):
        policy_path = (
            Path(__file__).resolve().parents[1]
            / "configs"
            / "dataset"
            / "dataset-lifecycle.policy.json"
        )
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["stage_dirs"]["raw"], "data/raw")
        self.assertEqual(payload["stage_dirs"]["interim"], "data/interim")
        self.assertEqual(payload["stage_dirs"]["curated"], "data/curated")
        self.assertEqual(payload["version_pattern"], "^v[0-9]+(?:\\.[0-9]+)*$")


if __name__ == "__main__":
    unittest.main()
