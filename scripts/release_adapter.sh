#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RUN_NAME=""
EVAL_SUMMARY=""
OUTPUT=""

usage() {
  cat <<'EOF'
Usage:
  release_adapter.sh --run-name <name> --eval-summary <path> --output <path>
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --run-name)
      RUN_NAME="$2"
      shift 2
      ;;
    --eval-summary)
      EVAL_SUMMARY="$2"
      shift 2
      ;;
    --output)
      OUTPUT="$2"
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

if [ -z "$RUN_NAME" ] || [ -z "$EVAL_SUMMARY" ] || [ -z "$OUTPUT" ]; then
  usage
  exit 1
fi

RUN_DIR="$ROOT_DIR/runs/$RUN_NAME"
if [ ! -d "$RUN_DIR" ]; then
  echo "Run directory not found: $RUN_DIR" >&2
  exit 1
fi

if [ ! -f "$EVAL_SUMMARY" ]; then
  echo "Eval summary not found: $EVAL_SUMMARY" >&2
  exit 1
fi

mkdir -p "$(dirname "$OUTPUT")"

python - "$RUN_NAME" "$EVAL_SUMMARY" "$OUTPUT" <<'PY'
import json
import sys
from datetime import datetime, timezone

run_name, eval_summary_path, output = sys.argv[1:4]
with open(eval_summary_path, "r", encoding="utf-8") as fh:
    summary = json.load(fh)

domain = str(summary.get("domain_eval", {}).get("verdict", "FAIL")).upper()
retention = str(summary.get("retention_eval", {}).get("verdict", "FAIL")).upper()
overall = str(summary.get("overall_verdict", "FAIL")).upper()

blocked = domain != "PASS" or retention != "PASS" or overall != "PASS"
payload = {
    "run_name": run_name,
    "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "domain_eval_verdict": domain,
    "retention_eval_verdict": retention,
    "overall_verdict": overall,
    "status": "blocked" if blocked else "released",
    "reason": "eval gates failed" if blocked else "all release gates passed",
}

with open(output, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=True, indent=2)
    fh.write("\n")

if blocked:
    raise SystemExit(1)
PY

echo "Release manifest written to $OUTPUT"
