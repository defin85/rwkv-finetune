import ast
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TRAIN_PY = REPO_ROOT / "third_party" / "RWKV-PEFT" / "train.py"
DATASET_PY = REPO_ROOT / "third_party" / "RWKV-PEFT" / "rwkvt" / "dataset" / "dataset.py"


class EpochStepsContractTests(unittest.TestCase):
    def setUp(self):
        if not TRAIN_PY.is_file() or not DATASET_PY.is_file():
            self.skipTest("RWKV-PEFT sources are not available in third_party/")

    def test_trainer_uses_limit_train_batches_from_epoch_steps(self):
        tree = ast.parse(TRAIN_PY.read_text(encoding="utf-8"))
        trainer_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Trainer"
        ]
        self.assertTrue(trainer_calls, "Trainer(...) call not found in train.py")

        has_limit_train_batches = False
        for call in trainer_calls:
            for kw in call.keywords:
                if kw.arg != "limit_train_batches":
                    continue
                value = kw.value
                if isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name):
                    has_limit_train_batches = value.value.id == "args" and value.attr == "epoch_steps"
        self.assertTrue(
            has_limit_train_batches,
            "Trainer must receive limit_train_batches=args.epoch_steps",
        )

    def test_dataset_loader_does_not_trim_to_epoch_steps(self):
        source = DATASET_PY.read_text(encoding="utf-8")
        self.assertNotIn("self.data = self.data[:args.epoch_steps]", source)
        self.assertNotIn("self.data = self.data.head(args.epoch_steps)", source)


if __name__ == "__main__":
    unittest.main()
