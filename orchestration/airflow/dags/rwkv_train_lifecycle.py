from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from airflow import DAG
from airflow.exceptions import AirflowFailException
from airflow.operators.python import PythonOperator


ROOT_DIR = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = ROOT_DIR / "scripts"
RUNS_DIR = ROOT_DIR / "runs"
DEFAULT_DAG_ID = os.getenv("AIRFLOW_DAG_ID", "rwkv_train_lifecycle")
GPU_POOL_NAME = os.getenv("AIRFLOW_GPU_POOL_NAME", "rwkv_gpu_pool")
AUDIT_DIR = Path(os.getenv("AIRFLOW_AUDIT_DIR", str(ROOT_DIR / "orchestration/airflow/runtime/audit")))
DEFAULT_INPUT_JSONL = str(ROOT_DIR / "data" / "raw" / "identity_hotfix_v3.jsonl")
DEFAULT_DATASET_MANIFEST = str(ROOT_DIR / "data" / "raw" / "identity_hotfix_v3.manifest.json")
DEFAULT_LOAD_MODEL = str(ROOT_DIR / "models" / "base" / "rwkv7-g1d-7.2b-20260131-ctx8192.pth")
DEFAULT_TRAIN_WRAPPER = str(SCRIPTS_DIR / "train_qlora_nf4_identity_safe.sh")

DEFAULT_RETRIES = int(os.getenv("AIRFLOW_TASK_RETRIES", "2"))
DEFAULT_RETRY_DELAY_SECONDS = int(os.getenv("AIRFLOW_RETRY_DELAY_SECONDS", "60"))
DEFAULT_MAX_RETRY_DELAY_SECONDS = int(os.getenv("AIRFLOW_MAX_RETRY_DELAY_SECONDS", "600"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _context_value(context: dict[str, Any], key: str, default: str = "") -> str:
    value = context.get(key, default)
    if value is None:
        return default
    return str(value)


def _context_run_id(context: dict[str, Any]) -> str:
    dag_run = context.get("dag_run")
    if dag_run and getattr(dag_run, "run_id", None):
        return str(dag_run.run_id)
    if context.get("run_id"):
        return str(context["run_id"])
    return f"manual-{_context_value(context, 'ts_nodash', 'unknown')}"


def _conf_or_env(conf: dict[str, Any], key: str, default: str = "") -> str:
    env_key = f"RWKV_AIRFLOW_{key.upper()}"
    if key in conf and conf[key] not in ("", None):
        return str(conf[key])
    return str(os.getenv(env_key, default))


def _dag_conf(context: dict[str, Any]) -> dict[str, Any]:
    dag_run = context.get("dag_run")
    conf = dict(dag_run.conf or {})
    ts_nodash = _context_value(context, "ts_nodash", datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"))
    run_name = _conf_or_env(conf, "run_name", f"airflow-{ts_nodash}")
    output_prefix = _conf_or_env(conf, "output_prefix", str(ROOT_DIR / "data" / "processed" / run_name))
    data_prefix = _conf_or_env(conf, "data_prefix", f"{output_prefix}_text_document")
    eval_summary_path = _conf_or_env(conf, "eval_summary_path", str(RUNS_DIR / run_name / "eval_summary.json"))
    release_manifest_path = _conf_or_env(conf, "release_manifest_path", str(RUNS_DIR / run_name / "release_manifest.json"))
    train_wrapper = _conf_or_env(conf, "train_wrapper", DEFAULT_TRAIN_WRAPPER)
    return {
        "run_name": run_name,
        "input_jsonl": _conf_or_env(conf, "input_jsonl", DEFAULT_INPUT_JSONL),
        "output_prefix": output_prefix,
        "data_prefix": data_prefix,
        "load_model": _conf_or_env(conf, "load_model", DEFAULT_LOAD_MODEL),
        "devices": _conf_or_env(conf, "devices", "1"),
        "wandb_project": _conf_or_env(conf, "wandb_project", ""),
        "train_wrapper": train_wrapper,
        "dataset_manifest": _conf_or_env(conf, "dataset_manifest", DEFAULT_DATASET_MANIFEST),
        "dataset_quality_status": _conf_or_env(conf, "dataset_quality_status", "PASS").upper(),
        "domain_eval_verdict": _conf_or_env(conf, "domain_eval_verdict", "PASS").upper(),
        "retention_eval_verdict": _conf_or_env(conf, "retention_eval_verdict", "PASS").upper(),
        "eval_summary_path": eval_summary_path,
        "release_manifest_path": release_manifest_path,
    }


def _require_fields(conf: dict[str, Any], fields: list[str], task_id: str) -> None:
    missing = [field for field in fields if not str(conf.get(field, "")).strip()]
    if missing:
        raise AirflowFailException(f"{task_id}: missing required config fields: {', '.join(missing)}")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def _audit_path(context: dict[str, Any], task_id: str) -> Path:
    run_id = _context_run_id(context).replace("/", "_")
    ti = context.get("ti")
    attempt = int(getattr(ti, "try_number", 1))
    return AUDIT_DIR / run_id / f"{task_id}-attempt-{attempt}.json"


def _write_audit(context: dict[str, Any], task_id: str, status: str, details: dict[str, Any]) -> None:
    ti = context.get("ti")
    payload = {
        "task_id": task_id,
        "status": status,
        "attempt": int(getattr(ti, "try_number", 1)),
        "dag_run_id": _context_run_id(context),
        "timestamp": _now_iso(),
        "details": details,
    }
    _write_json(_audit_path(context, task_id), payload)


def _run_shell(context: dict[str, Any], task_id: str, command: list[str]) -> None:
    env = dict(os.environ)
    env["ORCHESTRATION_PROFILE"] = "airflow"
    command_str = " ".join(command)
    try:
        subprocess.run(command, cwd=ROOT_DIR, check=True, env=env)
        _write_audit(context, task_id, "success", {"command": command_str})
    except subprocess.CalledProcessError as exc:
        _write_audit(
            context,
            task_id,
            "failed",
            {"command": command_str, "exit_code": exc.returncode},
        )
        raise AirflowFailException(f"{task_id} failed with exit code {exc.returncode}") from exc


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_gate_result(run_name: str, gate: str, verdict: str, reason: str) -> None:
    gate_path = RUNS_DIR / run_name / "gates" / f"{gate}.json"
    _write_json(
        gate_path,
        {
            "gate": gate,
            "verdict": verdict,
            "reason": reason,
            "created_at": _now_iso(),
        },
    )


def prepare_dataset(**context: Any) -> None:
    conf = _dag_conf(context)
    _require_fields(conf, ["input_jsonl", "output_prefix"], "prepare_dataset")
    command = [
        str(SCRIPTS_DIR / "prepare_binidx.sh"),
        conf["input_jsonl"],
        conf["output_prefix"],
    ]
    _run_shell(context, "prepare_dataset", command)

    data_prefix = conf["data_prefix"]
    expected_bin = Path(f"{data_prefix}.bin")
    expected_idx = Path(f"{data_prefix}.idx")
    if not expected_bin.is_file() or not expected_idx.is_file():
        reason = f"Expected binidx files not found for prefix: {data_prefix}"
        _write_audit(context, "prepare_dataset", "failed_artifact_validation", {"reason": reason})
        raise AirflowFailException(reason)

    _write_audit(
        context,
        "prepare_dataset",
        "validated",
        {"data_prefix": data_prefix, "bin": str(expected_bin), "idx": str(expected_idx)},
    )


def check_dataset_quality(**context: Any) -> None:
    conf = _dag_conf(context)
    status = conf["dataset_quality_status"]
    reason = f"dataset_quality_status={status}"

    if conf["dataset_manifest"]:
        manifest_path = Path(conf["dataset_manifest"])
        if not manifest_path.is_file():
            reason = f"dataset_manifest not found: {manifest_path}"
            _write_gate_result(conf["run_name"], "dataset_quality_gate", "FAIL", reason)
            _write_audit(context, "check_dataset_quality", "failed", {"reason": reason})
            raise AirflowFailException(reason)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        status = str(manifest.get("quality_status", status)).upper()
        expected_dataset = str(Path(conf["input_jsonl"]).resolve())
        manifest_dataset = str(manifest.get("dataset_path", "")).strip()
        if manifest_dataset and manifest_dataset != expected_dataset:
            reason = (
                "dataset_manifest dataset_path mismatch: "
                f"manifest={manifest_dataset}, expected={expected_dataset}"
            )
            _write_gate_result(conf["run_name"], "dataset_quality_gate", "FAIL", reason)
            _write_audit(context, "check_dataset_quality", "failed", {"reason": reason})
            raise AirflowFailException(reason)

        expected_sha = str(manifest.get("dataset_sha256", "")).strip().lower()
        if expected_sha:
            input_path = Path(conf["input_jsonl"])
            if not input_path.is_file():
                reason = f"input_jsonl not found for checksum verification: {input_path}"
                _write_gate_result(conf["run_name"], "dataset_quality_gate", "FAIL", reason)
                _write_audit(context, "check_dataset_quality", "failed", {"reason": reason})
                raise AirflowFailException(reason)
            actual_sha = _sha256_file(input_path).lower()
            if actual_sha != expected_sha:
                reason = (
                    "dataset_manifest checksum mismatch: "
                    f"manifest={expected_sha}, actual={actual_sha}"
                )
                _write_gate_result(conf["run_name"], "dataset_quality_gate", "FAIL", reason)
                _write_audit(context, "check_dataset_quality", "failed", {"reason": reason})
                raise AirflowFailException(reason)

        reason = f"dataset_manifest quality_status={status}"

    if status != "PASS":
        reason = f"Dataset quality gate failed: {reason}"
        _write_gate_result(conf["run_name"], "dataset_quality_gate", "FAIL", reason)
        _write_audit(context, "check_dataset_quality", "failed", {"reason": reason})
        raise AirflowFailException(reason)

    _write_gate_result(conf["run_name"], "dataset_quality_gate", "PASS", reason)
    _write_audit(context, "check_dataset_quality", "success", {"reason": reason})


def train_adapter(**context: Any) -> None:
    conf = _dag_conf(context)
    _require_fields(conf, ["train_wrapper", "load_model", "data_prefix", "run_name"], "train_adapter")
    wrapper = Path(conf["train_wrapper"])
    if not wrapper.is_file():
        raise AirflowFailException(f"train_wrapper not found: {wrapper}")

    command = [
        str(wrapper),
        "--load-model",
        conf["load_model"],
        "--data-prefix",
        conf["data_prefix"],
        "--run-name",
        conf["run_name"],
        "--devices",
        conf["devices"],
    ]
    if conf["wandb_project"]:
        command.extend(["--wandb", conf["wandb_project"]])

    _run_shell(context, "train_adapter", command)

    run_dir = RUNS_DIR / conf["run_name"]
    if not run_dir.is_dir():
        reason = f"Expected run directory not found: {run_dir}"
        _write_audit(context, "train_adapter", "failed_artifact_validation", {"reason": reason})
        raise AirflowFailException(reason)

    _write_audit(context, "train_adapter", "validated", {"run_dir": str(run_dir)})


def evaluate_adapter(**context: Any) -> None:
    conf = _dag_conf(context)
    _require_fields(conf, ["run_name", "eval_summary_path"], "evaluate_adapter")
    command = [
        str(SCRIPTS_DIR / "evaluate_adapter.sh"),
        "--run-name",
        conf["run_name"],
        "--domain-verdict",
        conf["domain_eval_verdict"],
        "--retention-verdict",
        conf["retention_eval_verdict"],
        "--output",
        conf["eval_summary_path"],
    ]
    _run_shell(context, "evaluate_adapter", command)

    summary_path = Path(conf["eval_summary_path"])
    if not summary_path.is_file():
        reason = f"Expected eval summary not found: {summary_path}"
        _write_audit(context, "evaluate_adapter", "failed_artifact_validation", {"reason": reason})
        raise AirflowFailException(reason)

    _write_audit(context, "evaluate_adapter", "validated", {"eval_summary_path": str(summary_path)})


def check_eval_gates(**context: Any) -> None:
    conf = _dag_conf(context)
    summary_path = Path(conf["eval_summary_path"])
    if not summary_path.is_file():
        reason = f"eval_summary_path not found: {summary_path}"
        _write_gate_result(conf["run_name"], "eval_gate", "FAIL", reason)
        _write_audit(context, "check_eval_gates", "failed", {"reason": reason})
        raise AirflowFailException(reason)

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    domain_verdict = str(summary.get("domain_eval", {}).get("verdict", "FAIL")).upper()
    retention_verdict = str(summary.get("retention_eval", {}).get("verdict", "FAIL")).upper()

    if domain_verdict != "PASS" or retention_verdict != "PASS":
        reason = (
            "Eval gates failed: "
            f"domain_eval={domain_verdict}, retention_eval={retention_verdict}"
        )
        _write_gate_result(conf["run_name"], "eval_gate", "FAIL", reason)
        _write_audit(context, "check_eval_gates", "failed", {"reason": reason})
        raise AirflowFailException(reason)

    reason = f"domain_eval={domain_verdict}, retention_eval={retention_verdict}"
    _write_gate_result(conf["run_name"], "eval_gate", "PASS", reason)
    _write_audit(context, "check_eval_gates", "success", {"reason": reason})


def release_adapter(**context: Any) -> None:
    conf = _dag_conf(context)
    _require_fields(conf, ["run_name", "eval_summary_path", "release_manifest_path"], "release_adapter")
    command = [
        str(SCRIPTS_DIR / "release_adapter.sh"),
        "--run-name",
        conf["run_name"],
        "--eval-summary",
        conf["eval_summary_path"],
        "--output",
        conf["release_manifest_path"],
    ]
    _run_shell(context, "release_adapter", command)

    release_manifest_path = Path(conf["release_manifest_path"])
    if not release_manifest_path.is_file():
        reason = f"Expected release manifest not found: {release_manifest_path}"
        _write_audit(context, "release_adapter", "failed_artifact_validation", {"reason": reason})
        raise AirflowFailException(reason)

    _write_audit(
        context,
        "release_adapter",
        "validated",
        {"release_manifest_path": str(release_manifest_path)},
    )


default_args = {
    "owner": "rwkv",
    "depends_on_past": False,
    "retries": DEFAULT_RETRIES,
    "retry_delay": timedelta(seconds=DEFAULT_RETRY_DELAY_SECONDS),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(seconds=DEFAULT_MAX_RETRY_DELAY_SECONDS),
}


with DAG(
    dag_id=DEFAULT_DAG_ID,
    default_args=default_args,
    start_date=datetime(2025, 1, 1),
    schedule=None,
    catchup=False,
    tags=["rwkv", "airflow", "training"],
    description="RWKV training lifecycle DAG: prepare_dataset -> train_adapter -> evaluate_adapter -> release_adapter",
) as dag:
    prepare_dataset_task = PythonOperator(
        task_id="prepare_dataset",
        python_callable=prepare_dataset,
    )

    check_dataset_quality_task = PythonOperator(
        task_id="check_dataset_quality",
        python_callable=check_dataset_quality,
    )

    train_adapter_task = PythonOperator(
        task_id="train_adapter",
        python_callable=train_adapter,
        pool=GPU_POOL_NAME,
    )

    evaluate_adapter_task = PythonOperator(
        task_id="evaluate_adapter",
        python_callable=evaluate_adapter,
        pool=GPU_POOL_NAME,
    )

    check_eval_gates_task = PythonOperator(
        task_id="check_eval_gates",
        python_callable=check_eval_gates,
    )

    release_adapter_task = PythonOperator(
        task_id="release_adapter",
        python_callable=release_adapter,
    )

    prepare_dataset_task >> check_dataset_quality_task >> train_adapter_task
    train_adapter_task >> evaluate_adapter_task >> check_eval_gates_task >> release_adapter_task
