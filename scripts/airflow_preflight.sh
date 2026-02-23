#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/airflow_common.sh"

REQUIRE_AIRFLOW=0
QUIET=0

usage() {
  cat <<'EOF'
Usage:
  airflow_preflight.sh [--require-airflow] [--quiet]

Options:
  --require-airflow  Fail if `airflow` CLI is not available in PATH
  --quiet            Suppress success output
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --require-airflow)
      REQUIRE_AIRFLOW=1
      shift
      ;;
    --quiet)
      QUIET=1
      shift
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

activate_venv_if_present

PYTHON_EXEC="$PYTHON_BIN"
if [ -x "$VENV_DIR/bin/python" ]; then
  PYTHON_EXEC="$VENV_DIR/bin/python"
fi

if ! command -v "$PYTHON_EXEC" >/dev/null 2>&1; then
  echo "Python executable not found: $PYTHON_EXEC" >&2
  exit 1
fi

PYTHON_VERSION="$("$PYTHON_EXEC" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')"

if ! "$PYTHON_EXEC" - "$AIRFLOW_SUPPORTED_PYTHON_MIN" "$AIRFLOW_SUPPORTED_PYTHON_MAX" <<'PY'
import sys

def parse(v: str) -> tuple[int, int]:
    parts = v.split(".")
    if len(parts) < 2:
        raise ValueError(f"invalid version: {v}")
    return int(parts[0]), int(parts[1])

py = sys.version_info[:2]
min_v = parse(sys.argv[1])
max_v = parse(sys.argv[2])

if py < min_v or py > max_v:
    print(
        f"Unsupported Python version {py[0]}.{py[1]} for Airflow runtime; "
        f"supported range is {min_v[0]}.{min_v[1]}..{max_v[0]}.{max_v[1]}",
        file=sys.stderr,
    )
    raise SystemExit(1)
PY
then
  cat >&2 <<EOF
Airflow preflight failed.
Detected Python: $PYTHON_VERSION
Supported range: ${AIRFLOW_SUPPORTED_PYTHON_MIN}..${AIRFLOW_SUPPORTED_PYTHON_MAX}
Remediation: use Python 3.9-3.12 for Airflow scripts in this repository.
EOF
  exit 1
fi

AIRFLOW_DETECTED="not-installed"
if command -v airflow >/dev/null 2>&1; then
  AIRFLOW_DETECTED="$(
    airflow version 2>/dev/null | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+' | head -n1 || true
  )"
  if [ -z "$AIRFLOW_DETECTED" ]; then
    AIRFLOW_DETECTED="unknown"
  fi

  if [ "$AIRFLOW_DETECTED" != "unknown" ] && ! "$PYTHON_EXEC" - "$AIRFLOW_DETECTED" <<'PY'
import re
import sys

match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", sys.argv[1].strip())
if not match:
    raise SystemExit(0)

major = int(match.group(1))
if major < 2:
    print(f"Unsupported Airflow major version: {major}", file=sys.stderr)
    raise SystemExit(1)
PY
  then
    echo "Airflow preflight failed: unsupported Airflow version ($AIRFLOW_DETECTED)." >&2
    exit 1
  fi
elif [ "$REQUIRE_AIRFLOW" = "1" ]; then
  echo "Airflow preflight failed: 'airflow' command not found in PATH." >&2
  exit 1
fi

if [ "$QUIET" = "0" ]; then
  echo "Airflow preflight OK (python=$PYTHON_VERSION, airflow=$AIRFLOW_DETECTED)"
fi
