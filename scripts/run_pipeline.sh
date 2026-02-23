#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/airflow_common.sh"

DAG_ID="${AIRFLOW_DAG_ID:-rwkv_train_lifecycle}"
RUN_ID=""
CONF_JSON=""
CONF_FILE=""

usage() {
  cat <<'EOF'
Usage:
  run_pipeline.sh [--dag-id <id>] [--run-id <id>] [--conf-json <json>] [--conf-file <path>]

Examples:
  ./scripts/run_pipeline.sh
  ./scripts/run_pipeline.sh --run-id rwkv-manual-001 --conf-json '{"run_name":"rwkv-manual-001"}'
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dag-id)
      DAG_ID="$2"
      shift 2
      ;;
    --run-id)
      RUN_ID="$2"
      shift 2
      ;;
    --conf-json)
      CONF_JSON="$2"
      shift 2
      ;;
    --conf-file)
      CONF_FILE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

require_primary_airflow
activate_venv_if_present
need_cmd airflow

if [ -n "$CONF_FILE" ] && [ -n "$CONF_JSON" ]; then
  echo "Use only one of --conf-file or --conf-json" >&2
  exit 1
fi

if [ -n "$CONF_FILE" ]; then
  if [ ! -f "$CONF_FILE" ]; then
    echo "Config file not found: $CONF_FILE" >&2
    exit 1
  fi
  CONF_JSON="$(cat "$CONF_FILE")"
fi

TRIGGER_CMD=(airflow dags trigger "$DAG_ID")

if [ -n "$RUN_ID" ]; then
  TRIGGER_CMD+=(--run-id "$RUN_ID")
fi

if [ -n "$CONF_JSON" ]; then
  TRIGGER_CMD+=(--conf "$CONF_JSON")
fi

printf 'Trigger command:'
printf ' %q' "${TRIGGER_CMD[@]}"
echo
"${TRIGGER_CMD[@]}"
