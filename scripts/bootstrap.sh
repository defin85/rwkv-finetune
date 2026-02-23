#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE_ENV="$ROOT_DIR/configs/workspace.env"

if [ -f "$WORKSPACE_ENV" ]; then
  # shellcheck disable=SC1090
  source "$WORKSPACE_ENV"
fi

RWKV_PEFT_REPO_URL="${RWKV_PEFT_REPO_URL:-https://github.com/JL-er/RWKV-PEFT.git}"
RWKV_PEFT_REF="${RWKV_PEFT_REF:-main}"
RWKV_PEFT_DIR="${RWKV_PEFT_DIR:-$ROOT_DIR/third_party/RWKV-PEFT}"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
TORCH_INDEX_URL="${TORCH_INDEX_URL:-https://download.pytorch.org/whl/cu124}"
INSTALL_DEEPSPEED="${INSTALL_DEEPSPEED:-1}"
INSTALL_BITSANDBYTES="${INSTALL_BITSANDBYTES:-1}"
SKIP_TORCH_INSTALL="${SKIP_TORCH_INSTALL:-0}"

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

need_cmd git
need_cmd "$PYTHON_BIN"

mkdir -p "$ROOT_DIR/third_party"

if [ ! -d "$RWKV_PEFT_DIR/.git" ]; then
  echo "Cloning RWKV-PEFT into $RWKV_PEFT_DIR"
  git clone "$RWKV_PEFT_REPO_URL" "$RWKV_PEFT_DIR"
fi

echo "Updating RWKV-PEFT ($RWKV_PEFT_REF)"
git -C "$RWKV_PEFT_DIR" fetch --tags --prune
git -C "$RWKV_PEFT_DIR" checkout "$RWKV_PEFT_REF"

if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtualenv in $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip setuptools wheel

if [ "$SKIP_TORCH_INSTALL" != "1" ]; then
  if ! python -m pip install torch --index-url "$TORCH_INDEX_URL"; then
    echo "Torch install from $TORCH_INDEX_URL failed; retrying from default PyPI index."
    python -m pip install torch
  fi
fi

python -m pip install -r "$RWKV_PEFT_DIR/requirements.txt"
python -m pip install -e "$RWKV_PEFT_DIR"
# RWKV-PEFT requirements miss json2binidx runtime deps used by prepare_binidx.sh.
python -m pip install lm_dataformat ftfy numpy tqdm tokenizers

if [ "$INSTALL_DEEPSPEED" = "1" ]; then
  python -m pip install deepspeed
fi

if [ "$INSTALL_BITSANDBYTES" = "1" ]; then
  python -m pip install bitsandbytes
fi

echo "Bootstrap completed."
echo "Next step: ./scripts/healthcheck.sh"
