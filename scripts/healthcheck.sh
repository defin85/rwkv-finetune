#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE_ENV="$ROOT_DIR/configs/workspace.env"

if [ -f "$WORKSPACE_ENV" ]; then
  # shellcheck disable=SC1090
  source "$WORKSPACE_ENV"
fi

VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"

if [ -f "$VENV_DIR/bin/activate" ]; then
  # shellcheck disable=SC1090
  source "$VENV_DIR/bin/activate"
fi

echo "=== GPU visibility ==="
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi
elif [ -x "/usr/lib/wsl/lib/nvidia-smi" ]; then
  /usr/lib/wsl/lib/nvidia-smi
else
  echo "nvidia-smi not found in PATH and /usr/lib/wsl/lib/nvidia-smi"
fi

echo
echo "=== Python / torch ==="
python - <<'PY'
import sys
print(f"python={sys.version.split()[0]}")
try:
    import torch
    print(f"torch={torch.__version__}")
    print(f"torch_cuda_build={torch.version.cuda}")
    print(f"cuda_available={torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"gpu_name={torch.cuda.get_device_name(0)}")
except Exception as exc:
    print(f"torch_check_failed={exc}")
PY

echo
echo "=== DeepSpeed ==="
if command -v ds_report >/dev/null 2>&1; then
  ds_report || true
else
  python - <<'PY'
try:
    import deepspeed
    print(f"deepspeed={deepspeed.__version__}")
except Exception as exc:
    print(f"deepspeed_not_available={exc}")
PY
fi

echo
echo "=== bitsandbytes ==="
python - <<'PY'
try:
    import bitsandbytes as bnb
    print(f"bitsandbytes={bnb.__version__}")
except Exception as exc:
    print(f"bitsandbytes_not_available={exc}")
PY

