import importlib.util
import json
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

    def tearDown(self):
        self.tmp.cleanup()

    def context(self, conf):
        return {
            "dag_run": FakeDagRun(conf),
            "ti": FakeTI(try_number=1),
            "run_id": "manual__test",
            "ts_nodash": "20260223T000000",
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
        with self.assertRaises(self.airflow_fail):
            self.module.check_dataset_quality(**self.context({"run_name": run_name, "dataset_quality_status": "FAIL"}))
        gate_path = self.module.RUNS_DIR / run_name / "gates" / "dataset_quality_gate.json"
        self.assertTrue(gate_path.is_file())
        payload = json.loads(gate_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["verdict"], "FAIL")

    def test_eval_gate_fail_raises_and_writes_fail_gate(self):
        run_name = "eval-fail"
        summary_path = self.module.RUNS_DIR / run_name / "eval_summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(
                {
                    "domain_eval": {"verdict": "PASS"},
                    "retention_eval": {"verdict": "FAIL"},
                    "overall_verdict": "FAIL",
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

    def test_eval_gate_pass_writes_pass_gate(self):
        run_name = "eval-pass"
        summary_path = self.module.RUNS_DIR / run_name / "eval_summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(
                {
                    "domain_eval": {"verdict": "PASS"},
                    "retention_eval": {"verdict": "PASS"},
                    "overall_verdict": "PASS",
                }
            ),
            encoding="utf-8",
        )

        self.module.check_eval_gates(**self.context({"run_name": run_name, "eval_summary_path": str(summary_path)}))

        gate_path = self.module.RUNS_DIR / run_name / "gates" / "eval_gate.json"
        self.assertTrue(gate_path.is_file())
        payload = json.loads(gate_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["verdict"], "PASS")


if __name__ == "__main__":
    unittest.main()
