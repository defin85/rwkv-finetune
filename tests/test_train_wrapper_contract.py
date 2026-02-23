import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


class TrainWrapperContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

        self.rwkv_peft_dir = self.root / "rwkv-peft"
        self.rwkv_peft_dir.mkdir(parents=True, exist_ok=True)
        (self.rwkv_peft_dir / "train.py").write_text(
            textwrap.dedent(
                """\
                import json
                import os
                import sys

                args = sys.argv[1:]
                proj_dir = None
                for i, arg in enumerate(args):
                    if arg == "--proj_dir" and i + 1 < len(args):
                        proj_dir = args[i + 1]
                        break

                if proj_dir is None:
                    raise SystemExit(2)

                os.makedirs(proj_dir, exist_ok=True)
                with open(os.path.join(proj_dir, "train_invocation.json"), "w", encoding="utf-8") as fh:
                    json.dump({"args": args}, fh, ensure_ascii=True, indent=2)
                    fh.write("\\n")
                """
            ),
            encoding="utf-8",
        )

        self.model_cfg = self.root / "model.env"
        self.model_cfg.write_text(
            textwrap.dedent(
                """\
                N_LAYER=1
                N_EMBD=8
                VOCAB_SIZE=100
                CTX_LEN=64
                """
            ),
            encoding="utf-8",
        )

        self.profile_cfg = self.root / "profile.env"
        self.profile_cfg.write_text(
            textwrap.dedent(
                """\
                MY_TESTING=dummy
                PEFT=lora
                PEFT_CONFIG=dummy
                QUANT=none
                PRECISION=bf16
                STRATEGY=auto
                MICRO_BSZ=1
                ACCUMULATE_GRAD_BATCHES=1
                GRAD_CP=0
                EPOCH_STEPS=1
                EPOCH_COUNT=1
                EPOCH_SAVE=1
                LR_INIT=0.0001
                LR_FINAL=0.00001
                OP=adamw
                """
            ),
            encoding="utf-8",
        )

        self.base_model = self.root / "base-model.pth"
        self.base_model.write_text("stub", encoding="utf-8")

        self.data_prefix = self.root / "sample_text_document"
        (self.root / "sample_text_document.bin").write_text("", encoding="utf-8")
        (self.root / "sample_text_document.idx").write_text("", encoding="utf-8")

        self.train_script = Path(__file__).resolve().parents[1] / "scripts" / "train.sh"

    def tearDown(self):
        self.tmp.cleanup()

    def test_train_sh_accepts_default_model_and_profile_from_env(self):
        env = os.environ.copy()
        env["RWKV_PEFT_DIR"] = str(self.rwkv_peft_dir)
        env["TRAIN_MODEL_CONFIG"] = str(self.model_cfg)
        env["TRAIN_PROFILE_CONFIG"] = str(self.profile_cfg)
        env["USE_WORKSPACE_ENV"] = "0"

        run_name = f"contract-run-defaults-{os.getpid()}"
        cmd = [
            str(self.train_script),
            "--load-model",
            str(self.base_model),
            "--data-prefix",
            str(self.data_prefix),
            "--run-name",
            run_name,
            "--devices",
            "1",
        ]

        result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
        self.assertEqual(
            result.returncode,
            0,
            msg=f"stdout:\\n{result.stdout}\\n\\nstderr:\\n{result.stderr}",
        )

        run_dir = Path(__file__).resolve().parents[1] / "runs" / run_name
        invocation = run_dir / "train_invocation.json"
        self.assertTrue(invocation.is_file())

        payload = json.loads(invocation.read_text(encoding="utf-8"))
        self.assertIn("--load_model", payload["args"])

        # Cleanup test artifact in repository run dir.
        if run_dir.exists():
            shutil.rmtree(run_dir)


if __name__ == "__main__":
    unittest.main()
