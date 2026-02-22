#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE_ENV="$ROOT_DIR/configs/workspace.env"

if [ -f "$WORKSPACE_ENV" ]; then
  # shellcheck disable=SC1090
  source "$WORKSPACE_ENV"
fi

VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
DEFAULT_MODEL="${ALBATROSS_MODEL:-}"
DEFAULT_PROMPT="${ALBATROSS_PROMPT:-User: explain recursion in Python. Assistant:}"
DEFAULT_TOKENS="${ALBATROSS_TOKENS:-128}"
DEFAULT_BATCH="${ALBATROSS_BATCH:-1}"

usage() {
  cat <<EOF
Usage:
  run_albatross.sh [--model <path>] [--prompt <text>] [--tokens <n>] [--batch <n>] [extra infer_albatross args]

Examples:
  ./scripts/run_albatross.sh --model /path/to/model.pth --prompt "User: hi Assistant:" --tokens 64
  ALBATROSS_MODEL=/path/to/model.pth ./scripts/run_albatross.sh

Notes:
  - If --model is omitted, ALBATROSS_MODEL env var is used.
  - Extra args are passed to scripts/infer_albatross.py (e.g. --auto-clone, --temperature 0.9).
EOF
}

MODEL="$DEFAULT_MODEL"
PROMPT="$DEFAULT_PROMPT"
TOKENS="$DEFAULT_TOKENS"
BATCH="$DEFAULT_BATCH"
EXTRA_ARGS=()

while [ "$#" -gt 0 ]; do
  case "$1" in
    --model)
      MODEL="$2"
      shift 2
      ;;
    --prompt)
      PROMPT="$2"
      shift 2
      ;;
    --tokens)
      TOKENS="$2"
      shift 2
      ;;
    --batch)
      BATCH="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

if [ -z "$MODEL" ]; then
  echo "Model is required. Pass --model or set ALBATROSS_MODEL in environment." >&2
  usage
  exit 1
fi

if [ -f "$VENV_DIR/bin/activate" ]; then
  # shellcheck disable=SC1090
  source "$VENV_DIR/bin/activate"
fi

CMD=(
  python "$ROOT_DIR/scripts/infer_albatross.py"
  --model "$MODEL"
  --prompt "$PROMPT"
  --tokens "$TOKENS"
  --batch "$BATCH"
)

if [ ${#EXTRA_ARGS[@]} -gt 0 ]; then
  CMD+=("${EXTRA_ARGS[@]}")
fi

echo "Running command:"
printf ' %q' "${CMD[@]}"
echo
echo

"${CMD[@]}"

