#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RUN_NAME=""
DOMAIN_VERDICT="PASS"
RETENTION_VERDICT="PASS"
OUTPUT=""

usage() {
  cat <<'EOF'
Usage:
  evaluate_adapter.sh --run-name <name> [--domain-verdict PASS|FAIL] [--retention-verdict PASS|FAIL] --output <path>
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

if [ -z "$RUN_NAME" ] || [ -z "$OUTPUT" ]; then
  usage
  exit 1
fi

case "$DOMAIN_VERDICT" in
  PASS|FAIL) ;;
  *)
    echo "Invalid --domain-verdict: $DOMAIN_VERDICT (expected PASS|FAIL)" >&2
    exit 1
    ;;
esac

case "$RETENTION_VERDICT" in
  PASS|FAIL) ;;
  *)
    echo "Invalid --retention-verdict: $RETENTION_VERDICT (expected PASS|FAIL)" >&2
    exit 1
    ;;
esac

RUN_DIR="$ROOT_DIR/runs/$RUN_NAME"
if [ ! -d "$RUN_DIR" ]; then
  echo "Run directory not found: $RUN_DIR" >&2
  exit 1
fi

OVERALL_VERDICT="PASS"
if [ "$DOMAIN_VERDICT" != "PASS" ] || [ "$RETENTION_VERDICT" != "PASS" ]; then
  OVERALL_VERDICT="FAIL"
fi

mkdir -p "$(dirname "$OUTPUT")"

python - "$RUN_NAME" "$DOMAIN_VERDICT" "$RETENTION_VERDICT" "$OVERALL_VERDICT" "$OUTPUT" <<'PY'
import json
import sys
from datetime import datetime, timezone

run_name, domain_verdict, retention_verdict, overall_verdict, output = sys.argv[1:6]
payload = {
    "run_name": run_name,
    "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "domain_eval": {"verdict": domain_verdict},
    "retention_eval": {"verdict": retention_verdict},
    "overall_verdict": overall_verdict,
}
with open(output, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=True, indent=2)
    fh.write("\n")
PY

echo "Evaluation summary written to $OUTPUT"
