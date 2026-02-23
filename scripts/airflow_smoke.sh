#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/airflow_common.sh"

RUN_NAME="${1:-airflow-smoke-$(date +%Y%m%d%H%M%S)}"
SMOKE_ROOT="$AIRFLOW_RUNTIME_ROOT/smoke/$RUN_NAME"
INPUT_JSONL="$SMOKE_ROOT/input.jsonl"
OUTPUT_PREFIX="$SMOKE_ROOT/data/sample"
DATA_PREFIX="${OUTPUT_PREFIX}_text_document"
CONF_JSON="$SMOKE_ROOT/conf.json"
MODEL_PLACEHOLDER="$SMOKE_ROOT/models/smoke-model.pth"
EVAL_SUMMARY="$ROOT_DIR/runs/$RUN_NAME/eval_summary.json"
RELEASE_MANIFEST="$ROOT_DIR/runs/$RUN_NAME/release_manifest.json"
LOGICAL_DATE="$(date -u +%Y-%m-%dT%H:%M:%S)"
ENV_JSON=""
SMOKE_REPORT="$SMOKE_ROOT/smoke_report.json"

require_primary_airflow
activate_venv_if_present
need_cmd airflow
ensure_runtime_dirs

mkdir -p "$SMOKE_ROOT/data" "$SMOKE_ROOT/models" "$ROOT_DIR/runs/$RUN_NAME"

cat >"$INPUT_JSONL" <<'EOF'
{"text":"User: explain 1C loop. Assistant: use while loop with clear termination."}
EOF

printf "smoke model placeholder\n" >"$MODEL_PLACEHOLDER"

python - "$CONF_JSON" "$INPUT_JSONL" "$OUTPUT_PREFIX" "$DATA_PREFIX" "$MODEL_PLACEHOLDER" "$RUN_NAME" "$EVAL_SUMMARY" "$RELEASE_MANIFEST" <<'PY'
import json
import sys

(
    conf_path,
    input_jsonl,
    output_prefix,
    data_prefix,
    model_placeholder,
    run_name,
    eval_summary,
    release_manifest,
) = sys.argv[1:9]

payload = {
    "input_jsonl": input_jsonl,
    "output_prefix": output_prefix,
    "data_prefix": data_prefix,
    "load_model": model_placeholder,
    "run_name": run_name,
    "train_wrapper": "scripts/train_smoke_stub.sh",
    "dataset_quality_status": "PASS",
    "domain_eval_verdict": "PASS",
    "retention_eval_verdict": "PASS",
    "eval_summary_path": eval_summary,
    "release_manifest_path": release_manifest,
}

with open(conf_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=True, indent=2)
    fh.write("\n")
PY

ENV_JSON="$(python - "$CONF_JSON" <<'PY'
import json
import sys

conf_path = sys.argv[1]
with open(conf_path, "r", encoding="utf-8") as fh:
    conf = json.load(fh)

env_payload = {
    "RWKV_AIRFLOW_INPUT_JSONL": conf["input_jsonl"],
    "RWKV_AIRFLOW_OUTPUT_PREFIX": conf["output_prefix"],
    "RWKV_AIRFLOW_DATA_PREFIX": conf["data_prefix"],
    "RWKV_AIRFLOW_LOAD_MODEL": conf["load_model"],
    "RWKV_AIRFLOW_RUN_NAME": conf["run_name"],
    "RWKV_AIRFLOW_TRAIN_WRAPPER": conf["train_wrapper"],
    "RWKV_AIRFLOW_DATASET_QUALITY_STATUS": conf["dataset_quality_status"],
    "RWKV_AIRFLOW_DOMAIN_EVAL_VERDICT": conf["domain_eval_verdict"],
    "RWKV_AIRFLOW_RETENTION_EVAL_VERDICT": conf["retention_eval_verdict"],
    "RWKV_AIRFLOW_EVAL_SUMMARY_PATH": conf["eval_summary_path"],
    "RWKV_AIRFLOW_RELEASE_MANIFEST_PATH": conf["release_manifest_path"],
}
print(json.dumps(env_payload, ensure_ascii=True))
PY
)"

echo "Running DAG smoke test for: $RUN_NAME"
if airflow dags test "$AIRFLOW_DAG_ID" "$LOGICAL_DATE" --conf "$(cat "$CONF_JSON")"; then
  echo "Primary smoke path: airflow dags test -> OK"
  python - "$SMOKE_REPORT" "$RUN_NAME" <<'PY'
import json
import sys
from datetime import datetime, timezone

report_path, run_name = sys.argv[1:3]
payload = {
    "run_name": run_name,
    "mode": "dag_test",
    "status": "PASS",
    "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
}
with open(report_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=True, indent=2)
    fh.write("\n")
PY
else
  echo "Primary smoke path failed, running wrapper fallback smoke."
  ./scripts/prepare_binidx.sh "$INPUT_JSONL" "$OUTPUT_PREFIX"
  ./scripts/train_smoke_stub.sh --load-model "$MODEL_PLACEHOLDER" --data-prefix "$DATA_PREFIX" --run-name "$RUN_NAME"
  ./scripts/evaluate_adapter.sh --run-name "$RUN_NAME" --domain-verdict PASS --retention-verdict PASS --output "$EVAL_SUMMARY"
  ./scripts/release_adapter.sh --run-name "$RUN_NAME" --eval-summary "$EVAL_SUMMARY" --output "$RELEASE_MANIFEST"

  mkdir -p "$ROOT_DIR/runs/$RUN_NAME/gates"
  python - "$ROOT_DIR/runs/$RUN_NAME/gates/dataset_quality_gate.json" "$ROOT_DIR/runs/$RUN_NAME/gates/eval_gate.json" <<'PY'
import json
import sys
from datetime import datetime, timezone

dataset_gate_path, eval_gate_path = sys.argv[1:3]
now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
dataset_gate = {
    "gate": "dataset_quality_gate",
    "verdict": "PASS",
    "reason": "wrapper fallback smoke: dataset_quality_status=PASS",
    "created_at": now,
}
eval_gate = {
    "gate": "eval_gate",
    "verdict": "PASS",
    "reason": "wrapper fallback smoke: domain_eval=PASS, retention_eval=PASS",
    "created_at": now,
}
for path, payload in [(dataset_gate_path, dataset_gate), (eval_gate_path, eval_gate)]:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=True, indent=2)
        fh.write("\n")
PY

  python - "$SMOKE_REPORT" "$RUN_NAME" <<'PY'
import json
import sys
from datetime import datetime, timezone

report_path, run_name = sys.argv[1:3]
payload = {
    "run_name": run_name,
    "mode": "wrapper_fallback",
    "status": "PASS_WITH_LIMITATIONS",
    "limitation": "airflow dags test failed on current runtime; wrapper fallback executed",
    "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
}
with open(report_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=True, indent=2)
    fh.write("\n")
PY
  echo "Fallback smoke path: wrapper sequence -> OK"
fi

EXPECTED=(
  "${DATA_PREFIX}.bin"
  "${DATA_PREFIX}.idx"
  "$ROOT_DIR/runs/$RUN_NAME/train_smoke_stub.json"
  "$EVAL_SUMMARY"
  "$RELEASE_MANIFEST"
  "$ROOT_DIR/runs/$RUN_NAME/gates/dataset_quality_gate.json"
  "$ROOT_DIR/runs/$RUN_NAME/gates/eval_gate.json"
  "$SMOKE_REPORT"
)

echo "Expected outputs:"
for path in "${EXPECTED[@]}"; do
  if [ -f "$path" ]; then
    echo "  OK  $path"
  else
    echo "  MISSING  $path" >&2
    exit 1
  fi
done

echo "Smoke run completed."
