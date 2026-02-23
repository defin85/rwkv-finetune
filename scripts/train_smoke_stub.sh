#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

LOAD_MODEL=""
DATA_PREFIX=""
RUN_NAME=""
DEVICES="1"
WANDB_PROJECT=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --load-model)
      LOAD_MODEL="$2"
      shift 2
      ;;
    --data-prefix)
      DATA_PREFIX="$2"
      shift 2
      ;;
    --run-name)
      RUN_NAME="$2"
      shift 2
      ;;
    --devices)
      DEVICES="$2"
      shift 2
      ;;
    --wandb)
      WANDB_PROJECT="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

if [ -z "$RUN_NAME" ] || [ -z "$DATA_PREFIX" ] || [ -z "$LOAD_MODEL" ]; then
  echo "train_smoke_stub requires --run-name, --data-prefix and --load-model" >&2
  exit 1
fi

if [ ! -f "${DATA_PREFIX}.bin" ] || [ ! -f "${DATA_PREFIX}.idx" ]; then
  echo "Missing binidx files for prefix: $DATA_PREFIX" >&2
  exit 1
fi

RUN_DIR="$ROOT_DIR/runs/$RUN_NAME"
mkdir -p "$RUN_DIR"

python - "$RUN_DIR/train_smoke_stub.json" "$RUN_NAME" "$LOAD_MODEL" "$DATA_PREFIX" "$DEVICES" "$WANDB_PROJECT" <<'PY'
import json
import sys
from datetime import datetime, timezone

out, run_name, load_model, data_prefix, devices, wandb_project = sys.argv[1:7]
payload = {
    "run_name": run_name,
    "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "load_model": load_model,
    "data_prefix": data_prefix,
    "devices": devices,
    "wandb_project": wandb_project,
    "status": "smoke_ok",
}
with open(out, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=True, indent=2)
    fh.write("\n")
PY

echo "Smoke train artifact written to $RUN_DIR/train_smoke_stub.json"
