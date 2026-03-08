import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path


def load_dag_module():
    module_name = "rwkv_airflow_dag_under_test"
    module_path = Path(__file__).resolve().parents[1] / "orchestration" / "airflow" / "dags" / "rwkv_train_lifecycle.py"

    class DummyDAG:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class DummyTask:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def __rshift__(self, other):
            return other

    class DummyAirflowFailException(Exception):
        pass

    for key in [
        "airflow",
        "airflow.exceptions",
        "airflow.operators",
        "airflow.operators.python",
    ]:
        sys.modules.pop(key, None)

    airflow_module = types.ModuleType("airflow")
    airflow_module.DAG = DummyDAG
    airflow_exceptions = types.ModuleType("airflow.exceptions")
    airflow_exceptions.AirflowFailException = DummyAirflowFailException
    airflow_operators = types.ModuleType("airflow.operators")
    airflow_operators_python = types.ModuleType("airflow.operators.python")
    airflow_operators_python.PythonOperator = DummyTask

    sys.modules["airflow"] = airflow_module
    sys.modules["airflow.exceptions"] = airflow_exceptions
    sys.modules["airflow.operators"] = airflow_operators
    sys.modules["airflow.operators.python"] = airflow_operators_python

    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module, DummyAirflowFailException


class FakeDagRun:
    def __init__(self, conf):
        self.conf = conf
        self.run_id = "manual__test"


class FakeTI:
    def __init__(self, try_number=1):
        self.try_number = try_number


class AirflowGateLogicTests(unittest.TestCase):
    def setUp(self):
        self.module, self.airflow_fail = load_dag_module()
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.module.RUNS_DIR = root / "runs"
        self.module.AUDIT_DIR = root / "audit"
        self._saved_env = {name: os.environ.get(name) for name in ["RWKV_AIRFLOW_INPUT_JSONL", "RWKV_AIRFLOW_DATASET_MANIFEST"]}
        os.environ.pop("RWKV_AIRFLOW_INPUT_JSONL", None)
        os.environ.pop("RWKV_AIRFLOW_DATASET_MANIFEST", None)

    def tearDown(self):
        for name, value in self._saved_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self.tmp.cleanup()

    def context(self, conf):
        return {
            "dag_run": FakeDagRun(conf),
            "ti": FakeTI(try_number=1),
            "run_id": "manual__test",
            "ts_nodash": "20260223T000000",
        }

    def eval_summary_payload(self, domain_verdict="PASS", retention_verdict="PASS"):
        overall_verdict = "PASS" if domain_verdict == "PASS" and retention_verdict == "PASS" else "FAIL"
        return {
            "overall_verdict": overall_verdict,
            "domain_eval": {
                "verdict": domain_verdict,
                "categories": {
                    "code_generation": {
                        "verdict": domain_verdict,
                        "score": 0.81,
                        "samples_total": 8,
                        "failures_total": 0 if domain_verdict == "PASS" else 2,
                    }
                },
            },
            "retention_eval": {
                "verdict": retention_verdict,
                "categories": {
                    "ru_general": {
                        "verdict": retention_verdict,
                        "score": 0.79,
                        "samples_total": 5,
                        "failures_total": 0 if retention_verdict == "PASS" else 1,
                    }
                },
            },
            "hard_cases": [],
        }

    def test_dataset_quality_pass_writes_pass_gate(self):
        run_name = "dataset-pass"
        self.module.check_dataset_quality(**self.context({"run_name": run_name, "dataset_quality_status": "PASS"}))
        gate_path = self.module.RUNS_DIR / run_name / "gates" / "dataset_quality_gate.json"
        self.assertTrue(gate_path.is_file())
        payload = json.loads(gate_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["verdict"], "PASS")

    def test_dataset_quality_fail_raises_and_writes_fail_gate(self):
        run_name = "dataset-fail"
        root = Path(self.tmp.name)
        manifest_path = root / "manifest-fail.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "quality_status": "FAIL",
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaises(self.airflow_fail):
            self.module.check_dataset_quality(
                **self.context(
                    {
                        "run_name": run_name,
                        "dataset_quality_status": "FAIL",
                        "dataset_manifest": str(manifest_path),
                    }
                )
            )
        gate_path = self.module.RUNS_DIR / run_name / "gates" / "dataset_quality_gate.json"
        self.assertTrue(gate_path.is_file())
        payload = json.loads(gate_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["verdict"], "FAIL")

    def test_dataset_manifest_path_mismatch_without_checksum_fails(self):
        run_name = "dataset-path-mismatch"
        root = Path(self.tmp.name)
        dataset_path = root / "data.jsonl"
        dataset_path.write_text('{"text":"User: test\\nAssistant: ok"}\n', encoding="utf-8")

        manifest_path = root / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "dataset_path": "/tmp/other-location/data.jsonl",
                    "quality_status": "PASS",
                }
            ),
            encoding="utf-8",
        )

        with self.assertRaises(self.airflow_fail):
            self.module.check_dataset_quality(
                **self.context(
                    {
                        "run_name": run_name,
                        "dataset_quality_status": "PASS",
                        "input_jsonl": str(dataset_path),
                        "dataset_manifest": str(manifest_path),
                    }
                )
            )

        gate_path = self.module.RUNS_DIR / run_name / "gates" / "dataset_quality_gate.json"
        self.assertTrue(gate_path.is_file())
        payload = json.loads(gate_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["verdict"], "FAIL")

    def test_eval_gate_fail_raises_and_writes_fail_gate(self):
        run_name = "eval-fail"
        summary_path = self.module.RUNS_DIR / run_name / "eval_summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(self.eval_summary_payload(domain_verdict="PASS", retention_verdict="FAIL")),
            encoding="utf-8",
        )

        with self.assertRaises(self.airflow_fail):
            self.module.check_eval_gates(
                **self.context({"run_name": run_name, "eval_summary_path": str(summary_path)})
            )

        gate_path = self.module.RUNS_DIR / run_name / "gates" / "eval_gate.json"
        self.assertTrue(gate_path.is_file())
        payload = json.loads(gate_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["verdict"], "FAIL")

    def test_eval_gate_pass_writes_pass_gate(self):
        run_name = "eval-pass"
        summary_path = self.module.RUNS_DIR / run_name / "eval_summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(self.eval_summary_payload()),
            encoding="utf-8",
        )

        self.module.check_eval_gates(**self.context({"run_name": run_name, "eval_summary_path": str(summary_path)}))

        gate_path = self.module.RUNS_DIR / run_name / "gates" / "eval_gate.json"
        self.assertTrue(gate_path.is_file())
        payload = json.loads(gate_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["verdict"], "PASS")

    def test_eval_gate_fails_closed_when_category_summaries_missing(self):
        run_name = "eval-missing-categories"
        summary_path = self.module.RUNS_DIR / run_name / "eval_summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(
                {
                    "domain_eval": {"verdict": "PASS"},
                    "retention_eval": {"verdict": "PASS"},
                    "overall_verdict": "PASS",
                    "hard_cases": [],
                }
            ),
            encoding="utf-8",
        )

        with self.assertRaises(self.airflow_fail):
            self.module.check_eval_gates(
                **self.context({"run_name": run_name, "eval_summary_path": str(summary_path)})
            )

        gate_path = self.module.RUNS_DIR / run_name / "gates" / "eval_gate.json"
        self.assertTrue(gate_path.is_file())
        payload = json.loads(gate_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["verdict"], "FAIL")

    def test_produce_eval_artifacts_runs_runtime_producer_and_validates_outputs(self):
        run_name = "eval-producer-pass"
        run_dir = self.module.RUNS_DIR / run_name
        run_dir.mkdir(parents=True, exist_ok=True)
        root = Path(self.tmp.name)
        domain_eval_jsonl = root / "domain_eval.jsonl"
        retention_eval_jsonl = root / "retention_eval.jsonl"
        eval_model_path = root / "eval-model.pth"
        inference_script = root / "stub_infer.py"
        domain_output = run_dir / "domain_eval.categories.json"
        retention_output = run_dir / "retention_eval.categories.json"
        hard_cases_output = run_dir / "hard_cases.json"

        domain_eval_jsonl.write_text('{"text":"User: test\\nAssistant: ok"}\n', encoding="utf-8")
        retention_eval_jsonl.write_text('{"text":"User: test\\nAssistant: ok"}\n', encoding="utf-8")
        eval_model_path.write_text("stub", encoding="utf-8")
        inference_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

        captured: dict[str, object] = {}

        def fake_run_shell(context, task_id, command):
            captured["task_id"] = task_id
            captured["command"] = command
            domain_output.write_text("{}", encoding="utf-8")
            retention_output.write_text("{}", encoding="utf-8")
            hard_cases_output.write_text("[]", encoding="utf-8")

        self.module._run_shell = fake_run_shell

        self.module.produce_eval_artifacts(
            **self.context(
                {
                    "run_name": run_name,
                    "eval_model_path": str(eval_model_path),
                    "domain_eval_jsonl": str(domain_eval_jsonl),
                    "retention_eval_jsonl": str(retention_eval_jsonl),
                    "eval_inference_script": str(inference_script),
                    "domain_categories_path": str(domain_output),
                    "retention_categories_path": str(retention_output),
                    "hard_cases_path": str(hard_cases_output),
                    "eval_tokens": "48",
                }
            )
        )

        self.assertEqual(captured["task_id"], "produce_eval_artifacts")
        self.assertEqual(
            captured["command"],
            [
                sys.executable,
                str(self.module.SCRIPTS_DIR / "produce_eval_artifacts.py"),
                "--run-name",
                run_name,
                "--run-dir",
                str(run_dir),
                "--model",
                str(eval_model_path),
                "--domain-eval-jsonl",
                str(domain_eval_jsonl),
                "--retention-eval-jsonl",
                str(retention_eval_jsonl),
                "--domain-output",
                str(domain_output),
                "--retention-output",
                str(retention_output),
                "--hard-cases-output",
                str(hard_cases_output),
                "--inference-script",
                str(inference_script),
                "--tokens",
                "48",
            ],
        )
        self.assertTrue(domain_output.is_file())
        self.assertTrue(retention_output.is_file())
        self.assertTrue(hard_cases_output.is_file())

    def test_produce_eval_artifacts_fails_closed_when_eval_inputs_missing(self):
        run_name = "eval-producer-missing"
        run_dir = self.module.RUNS_DIR / run_name
        run_dir.mkdir(parents=True, exist_ok=True)
        root = Path(self.tmp.name)
        eval_model_path = root / "eval-model.pth"
        inference_script = root / "stub_infer.py"
        eval_model_path.write_text("stub", encoding="utf-8")
        inference_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

        with self.assertRaises(self.airflow_fail):
            self.module.produce_eval_artifacts(
                **self.context(
                    {
                        "run_name": run_name,
                        "eval_model_path": str(eval_model_path),
                        "retention_eval_jsonl": str(root / "retention_eval.jsonl"),
                        "eval_inference_script": str(inference_script),
                    }
                )
            )

    def test_evaluate_adapter_omits_verdict_flags_when_not_configured(self):
        run_name = "eval-command-derived"
        run_dir = self.module.RUNS_DIR / run_name
        run_dir.mkdir(parents=True, exist_ok=True)
        root = Path(self.tmp.name)
        domain_categories = root / "domain_categories.json"
        retention_categories = root / "retention_categories.json"
        hard_cases = root / "hard_cases.json"
        output = root / "eval_summary.json"

        domain_categories.write_text("{}", encoding="utf-8")
        retention_categories.write_text("{}", encoding="utf-8")
        hard_cases.write_text("[]", encoding="utf-8")

        captured: dict[str, object] = {}

        def fake_run_shell(context, task_id, command):
            captured["task_id"] = task_id
            captured["command"] = command
            output.write_text(
                json.dumps(self.eval_summary_payload()),
                encoding="utf-8",
            )

        self.module._run_shell = fake_run_shell

        self.module.evaluate_adapter(
            **self.context(
                {
                    "run_name": run_name,
                    "domain_categories_path": str(domain_categories),
                    "retention_categories_path": str(retention_categories),
                    "hard_cases_path": str(hard_cases),
                    "eval_summary_path": str(output),
                }
            )
        )

        self.assertEqual(captured["task_id"], "evaluate_adapter")
        self.assertEqual(
            captured["command"],
            [
                str(self.module.SCRIPTS_DIR / "evaluate_adapter.sh"),
                "--run-name",
                run_name,
                "--domain-categories",
                str(domain_categories),
                "--retention-categories",
                str(retention_categories),
                "--hard-cases",
                str(hard_cases),
                "--output",
                str(output),
            ],
        )


if __name__ == "__main__":
    unittest.main()
