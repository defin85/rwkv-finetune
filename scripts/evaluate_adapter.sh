#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RUN_NAME=""
DOMAIN_VERDICT=""
RETENTION_VERDICT=""
DOMAIN_CATEGORIES=""
RETENTION_CATEGORIES=""
HARD_CASES=""
OUTPUT=""

usage() {
  cat <<'EOF'
Usage:
  evaluate_adapter.sh --run-name <name> [--domain-verdict PASS|FAIL] [--retention-verdict PASS|FAIL] \
    --domain-categories <path> --retention-categories <path> --hard-cases <path> --output <path>
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --run-name)
      RUN_NAME="$2"
      shift 2
      ;;
    --domain-verdict)
      DOMAIN_VERDICT="${2^^}"
      shift 2
      ;;
    --retention-verdict)
      RETENTION_VERDICT="${2^^}"
      shift 2
      ;;
    --domain-categories)
      DOMAIN_CATEGORIES="$2"
      shift 2
      ;;
    --retention-categories)
      RETENTION_CATEGORIES="$2"
      shift 2
      ;;
    --hard-cases)
      HARD_CASES="$2"
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

if [ -z "$RUN_NAME" ] || [ -z "$DOMAIN_CATEGORIES" ] || [ -z "$RETENTION_CATEGORIES" ] || [ -z "$HARD_CASES" ] || [ -z "$OUTPUT" ]; then
  usage
  exit 1
fi

if [ -n "$DOMAIN_VERDICT" ]; then
  case "$DOMAIN_VERDICT" in
    PASS|FAIL) ;;
    *)
      echo "Invalid --domain-verdict: $DOMAIN_VERDICT (expected PASS|FAIL)" >&2
      exit 1
      ;;
  esac
fi

if [ -n "$RETENTION_VERDICT" ]; then
  case "$RETENTION_VERDICT" in
    PASS|FAIL) ;;
    *)
      echo "Invalid --retention-verdict: $RETENTION_VERDICT (expected PASS|FAIL)" >&2
      exit 1
      ;;
  esac
fi

RUN_DIR="$ROOT_DIR/runs/$RUN_NAME"
if [ ! -d "$RUN_DIR" ]; then
  echo "Run directory not found: $RUN_DIR" >&2
  exit 1
fi

for artifact in "$DOMAIN_CATEGORIES" "$RETENTION_CATEGORIES" "$HARD_CASES"; do
  if [ ! -f "$artifact" ]; then
    echo "Evaluation artifact not found: $artifact" >&2
    exit 1
  fi
done

mkdir -p "$(dirname "$OUTPUT")"

python - "$ROOT_DIR" "$RUN_NAME" "$DOMAIN_VERDICT" "$RETENTION_VERDICT" "$DOMAIN_CATEGORIES" "$RETENTION_CATEGORIES" "$HARD_CASES" "$OUTPUT" <<'PY'
import json
import sys
from pathlib import Path

root_dir, run_name, domain_verdict, retention_verdict, domain_categories_path, retention_categories_path, hard_cases_path, output = sys.argv[1:9]
scripts_dir = Path(root_dir) / "scripts"
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from eval_summary_contract import build_eval_summary, read_json_file

payload = build_eval_summary(
    run_name=run_name,
    domain_verdict=domain_verdict or None,
    retention_verdict=retention_verdict or None,
    domain_categories=read_json_file(domain_categories_path),
    retention_categories=read_json_file(retention_categories_path),
    hard_cases=read_json_file(hard_cases_path),
)
with open(output, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=True, indent=2)
    fh.write("\n")
PY

echo "Evaluation summary written to $OUTPUT"
