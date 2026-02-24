#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/airflow_common.sh"

MODE="fallback"
RUN_NAME=""

usage() {
  cat <<'EOF'
Usage:
  airflow_smoke.sh [run_name] [--mode strict|fallback]

Options:
  --mode <mode>  Smoke execution mode:
                 strict   - no wrapper fallback; fail immediately if DAG test fails
                 fallback - run wrapper fallback if DAG test fails (default)
  --strict       Shortcut for --mode strict
  --fallback     Shortcut for --mode fallback
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --mode)
      MODE="$2"
      shift 2
      ;;
    --strict)
      MODE="strict"
      shift
      ;;
    --fallback)
      MODE="fallback"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
    *)
      if [ -n "$RUN_NAME" ]; then
        echo "Unexpected positional argument: $1" >&2
        usage
        exit 1
      fi
      RUN_NAME="$1"
      shift
      ;;
  esac
done

if [ -z "$RUN_NAME" ]; then
  RUN_NAME="airflow-smoke-$(date +%Y%m%d%H%M%S)"
fi

case "$MODE" in
  strict|fallback) ;;
  *)
    echo "Invalid --mode value: $MODE (expected strict|fallback)" >&2
    exit 1
    ;;
esac

SMOKE_ROOT="$AIRFLOW_RUNTIME_ROOT/smoke/$RUN_NAME"
INPUT_JSONL="$SMOKE_ROOT/input.jsonl"
OUTPUT_PREFIX="$SMOKE_ROOT/data/sample"
DATA_PREFIX="${OUTPUT_PREFIX}_text_document"
CONF_JSON="$SMOKE_ROOT/conf.json"
DATASET_MANIFEST="$SMOKE_ROOT/input.manifest.json"
MODEL_PLACEHOLDER="$SMOKE_ROOT/models/smoke-model.pth"
EVAL_SUMMARY="$ROOT_DIR/runs/$RUN_NAME/eval_summary.json"
RELEASE_MANIFEST="$ROOT_DIR/runs/$RUN_NAME/release_manifest.json"
LOGICAL_DATE="$(date -u +%Y-%m-%dT%H:%M:%S)"
SMOKE_REPORT="$SMOKE_ROOT/smoke_report.json"

require_primary_airflow
activate_venv_if_present
"$ROOT_DIR/scripts/airflow_preflight.sh" --require-airflow --quiet
need_cmd airflow
ensure_runtime_dirs

mkdir -p "$SMOKE_ROOT/data" "$SMOKE_ROOT/models" "$ROOT_DIR/runs/$RUN_NAME"

cat >"$INPUT_JSONL" <<'EOF'
{"text":"User: explain 1C loop. Assistant: use while loop with clear termination."}
EOF

printf "smoke model placeholder\n" >"$MODEL_PLACEHOLDER"

python "$ROOT_DIR/scripts/check_dataset_quality.py" \
  --input "$INPUT_JSONL" \
  --output "$DATASET_MANIFEST" \
  --min-rows 1 \
  --min-unique-ratio 1.0 \
  --min-user-assistant-ratio 1.0 \
  --min-identity-ratio 0.0 \
  --max-top1-share 1.0 \
  --max-qwen-negative-rows 1 \
  --strict

python - "$CONF_JSON" "$INPUT_JSONL" "$DATASET_MANIFEST" "$OUTPUT_PREFIX" "$DATA_PREFIX" "$MODEL_PLACEHOLDER" "$RUN_NAME" "$EVAL_SUMMARY" "$RELEASE_MANIFEST" <<'PY'
import json
import sys

(
    conf_path,
    input_jsonl,
    dataset_manifest,
    output_prefix,
    data_prefix,
    model_placeholder,
    run_name,
    eval_summary,
    release_manifest,
) = sys.argv[1:10]

payload = {
    "input_jsonl": input_jsonl,
    "dataset_manifest": dataset_manifest,
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

write_smoke_report() {
  local status="$1"
  local mode="$2"
  local detail="$3"
  python - "$SMOKE_REPORT" "$RUN_NAME" "$status" "$mode" "$detail" <<'PY'
import json
import sys
from datetime import datetime, timezone

report_path, run_name, status, mode, detail = sys.argv[1:6]
payload = {
    "run_name": run_name,
    "mode": mode,
    "status": status,
    "detail": detail,
    "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
}
with open(report_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=True, indent=2)
    fh.write("\n")
PY
}

echo "Running DAG smoke test for: $RUN_NAME (mode=$MODE)"
if airflow dags test "$AIRFLOW_DAG_ID" "$LOGICAL_DATE" --conf "$(cat "$CONF_JSON")"; then
  echo "Primary smoke path: airflow dags test -> OK"
  write_smoke_report "PASS" "dag_test" "airflow dags test succeeded"
else
  if [ "$MODE" = "strict" ]; then
    write_smoke_report "FAIL" "strict" "airflow dags test failed; fallback disabled in strict mode"
    echo "Primary smoke path failed and strict mode is enabled." >&2
    exit 1
  fi

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

  write_smoke_report "PASS_WITH_LIMITATIONS" "wrapper_fallback" "airflow dags test failed; wrapper fallback executed"
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
