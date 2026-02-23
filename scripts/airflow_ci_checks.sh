#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

bash -n \
  scripts/airflow_common.sh \
  scripts/airflow_preflight.sh \
  scripts/airflow_bootstrap.sh \
  scripts/airflow_services.sh \
  scripts/run_pipeline.sh \
  scripts/airflow_smoke.sh \
  scripts/evaluate_adapter.sh \
  scripts/release_adapter.sh \
  scripts/train_smoke_stub.sh \
  scripts/train.sh

python -m py_compile orchestration/airflow/dags/rwkv_train_lifecycle.py
python -m unittest discover -s tests -p "test_*.py"

if command -v airflow >/dev/null 2>&1; then
  airflow_json="$(airflow dags list-import-errors -o json -l 2>/dev/null || true)"
  python - "$airflow_json" <<'PY'
import json
import sys

raw = sys.argv[1].strip()
if not raw:
    raise SystemExit(0)

try:
    payload = json.loads(raw)
except json.JSONDecodeError:
    # Non-JSON output is ignored to keep this check portable across Airflow versions.
    raise SystemExit(0)

if isinstance(payload, list) and payload:
    print("Airflow DAG import errors detected:", file=sys.stderr)
    print(json.dumps(payload, ensure_ascii=True, indent=2), file=sys.stderr)
    raise SystemExit(1)
PY
fi

echo "airflow_ci_checks: OK"
