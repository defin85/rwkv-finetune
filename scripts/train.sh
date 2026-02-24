#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE_ENV="$ROOT_DIR/configs/workspace.env"

if [ "${USE_WORKSPACE_ENV:-1}" = "1" ] && [ -f "$WORKSPACE_ENV" ]; then
  # shellcheck disable=SC1090
  source "$WORKSPACE_ENV"
fi

RWKV_PEFT_DIR="${RWKV_PEFT_DIR:-$ROOT_DIR/third_party/RWKV-PEFT}"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
CUDA_HOME="${CUDA_HOME:-/opt/cuda}"

if [ -d "$CUDA_HOME/bin" ]; then
  export CUDA_HOME
  export PATH="$CUDA_HOME/bin:$PATH"
fi
if [ -d "$CUDA_HOME/lib64" ]; then
  if [ -n "${LD_LIBRARY_PATH:-}" ]; then
    export LD_LIBRARY_PATH="$CUDA_HOME/lib64:$LD_LIBRARY_PATH"
  else
    export LD_LIBRARY_PATH="$CUDA_HOME/lib64"
  fi
fi

MODEL_CONFIG=""
PROFILE_CONFIG=""
LOAD_MODEL=""
DATA_PREFIX=""
RUN_NAME=""
DEVICES="${DEVICES:-1}"
WANDB_PROJECT="${WANDB_PROJECT:-}"
DEFAULT_MODEL_CONFIG="${TRAIN_MODEL_CONFIG:-$ROOT_DIR/configs/model/rwkv7-7.2b.env}"
DEFAULT_PROFILE_CONFIG="${TRAIN_PROFILE_CONFIG:-$ROOT_DIR/configs/profile/lora-bf16.env}"

usage() {
  cat <<'EOF'
Usage:
  train.sh [--model <model.env>] [--profile <profile.env>] --load-model <base_model.pth> --data-prefix <binidx_prefix> [--run-name <name>] [--devices <n>] [--wandb <project>]

Example:
  ./scripts/train.sh \
    --load-model ./models/base/rwkv7-g1d-7.2b-20260131-ctx8192.pth \
    --data-prefix ./data/processed/sample_text_document \
    --run-name exp-rwkv7-qlora
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --model)
      MODEL_CONFIG="$2"
      shift 2
      ;;
    --profile)
      PROFILE_CONFIG="$2"
      shift 2
      ;;
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

if [ -z "$LOAD_MODEL" ] || [ -z "$DATA_PREFIX" ]; then
  usage
  exit 1
fi

if [ -z "$MODEL_CONFIG" ]; then
  MODEL_CONFIG="$DEFAULT_MODEL_CONFIG"
  echo "Using default model config: $MODEL_CONFIG"
fi

if [ -z "$PROFILE_CONFIG" ]; then
  PROFILE_CONFIG="$DEFAULT_PROFILE_CONFIG"
  echo "Using default profile config: $PROFILE_CONFIG"
fi

if [ ! -f "$MODEL_CONFIG" ]; then
  echo "Model config not found: $MODEL_CONFIG" >&2
  exit 1
fi

if [ ! -f "$PROFILE_CONFIG" ]; then
  echo "Profile config not found: $PROFILE_CONFIG" >&2
  exit 1
fi

if [ ! -f "$LOAD_MODEL" ]; then
  echo "Base model checkpoint not found: $LOAD_MODEL" >&2
  exit 1
fi

if [ ! -f "${DATA_PREFIX}.bin" ] || [ ! -f "${DATA_PREFIX}.idx" ]; then
  echo "Binidx files not found for prefix: $DATA_PREFIX" >&2
  echo "Expected: ${DATA_PREFIX}.bin and ${DATA_PREFIX}.idx" >&2
  exit 1
fi

if [ ! -f "$RWKV_PEFT_DIR/train.py" ]; then
  echo "RWKV-PEFT not found at: $RWKV_PEFT_DIR" >&2
  echo "Run ./scripts/bootstrap.sh first." >&2
  exit 1
fi

if [ -f "$VENV_DIR/bin/activate" ]; then
  # shellcheck disable=SC1090
  source "$VENV_DIR/bin/activate"
fi

# shellcheck disable=SC1090
source "$MODEL_CONFIG"
# shellcheck disable=SC1090
source "$PROFILE_CONFIG"

require_var() {
  local name="$1"
  if [ -z "${!name:-}" ]; then
    echo "Missing required variable '$name' in config files" >&2
    exit 1
  fi
}

require_var N_LAYER
require_var N_EMBD
require_var VOCAB_SIZE
require_var CTX_LEN
require_var MY_TESTING
require_var PEFT
require_var PEFT_CONFIG
require_var QUANT
require_var PRECISION
require_var STRATEGY
require_var MICRO_BSZ
require_var ACCUMULATE_GRAD_BATCHES
require_var GRAD_CP
require_var EPOCH_STEPS
require_var EPOCH_COUNT
require_var EPOCH_SAVE
require_var LR_INIT
require_var LR_FINAL
require_var OP

if [ -z "$RUN_NAME" ]; then
  RUN_NAME="$(date +%Y%m%d-%H%M%S)-${MODEL_TAG:-rwkv}-${PEFT}-${QUANT}"
fi

PROJ_DIR="$ROOT_DIR/runs/$RUN_NAME"
mkdir -p "$PROJ_DIR"

CMD=(
  python train.py
  --load_model "$LOAD_MODEL"
  --proj_dir "$PROJ_DIR"
  --data_file "$DATA_PREFIX"
  --data_type binidx
  --vocab_size "$VOCAB_SIZE"
  --n_layer "$N_LAYER"
  --n_embd "$N_EMBD"
  --ctx_len "$CTX_LEN"
  --micro_bsz "$MICRO_BSZ"
  --epoch_steps "$EPOCH_STEPS"
  --epoch_count "$EPOCH_COUNT"
  --epoch_save "$EPOCH_SAVE"
  --lr_init "$LR_INIT"
  --lr_final "$LR_FINAL"
  --accelerator gpu
  --precision "$PRECISION"
  --devices "$DEVICES"
  --strategy "$STRATEGY"
  --grad_cp "$GRAD_CP"
  --my_testing "$MY_TESTING"
  --peft "$PEFT"
  --peft_config "$PEFT_CONFIG"
  --quant "$QUANT"
  --accumulate_grad_batches "$ACCUMULATE_GRAD_BATCHES"
  --op "$OP"
)

if [ -n "${TRAIN_TYPE:-}" ] && [ "${TRAIN_TYPE:-none}" != "none" ]; then
  CMD+=(--train_type "$TRAIN_TYPE")
fi

if [ -n "${CHUNK_CTX:-}" ]; then
  CMD+=(--chunk_ctx "$CHUNK_CTX")
fi

if [ -n "$WANDB_PROJECT" ]; then
  CMD+=(--wandb "$WANDB_PROJECT")
fi

if [ "${FUSED_KERNEL:-0}" = "1" ]; then
  CMD+=(--fused_kernel)
fi

echo "Running command:"
printf ' %q' "${CMD[@]}"
echo
echo

(
  cd "$RWKV_PEFT_DIR"
  "${CMD[@]}"
)
