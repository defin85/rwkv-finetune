#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE_ENV="$ROOT_DIR/configs/workspace.env"

if [ -f "$WORKSPACE_ENV" ]; then
  # shellcheck disable=SC1090
  source "$WORKSPACE_ENV"
fi

RWKV_PEFT_DIR="${RWKV_PEFT_DIR:-$ROOT_DIR/third_party/RWKV-PEFT}"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
WORKERS="${WORKERS:-4}"

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
  echo "Usage: $0 <input.jsonl> <output_prefix> [tokenizer_vocab_file]" >&2
  exit 1
fi

INPUT_JSONL="$1"
OUTPUT_PREFIX="$2"
TOKENIZER_FILE="${3:-$RWKV_PEFT_DIR/json2binidx_tool/rwkv_vocab_v20230424.txt}"

if [ ! -f "$INPUT_JSONL" ]; then
  echo "Input JSONL not found: $INPUT_JSONL" >&2
  exit 1
fi

if [ ! -d "$RWKV_PEFT_DIR/json2binidx_tool" ]; then
  echo "RWKV-PEFT json2binidx_tool not found at $RWKV_PEFT_DIR/json2binidx_tool" >&2
  echo "Run ./scripts/bootstrap.sh first." >&2
  exit 1
fi

if [ ! -f "$TOKENIZER_FILE" ]; then
  echo "Tokenizer vocab file not found: $TOKENIZER_FILE" >&2
  exit 1
fi

if [ -f "$VENV_DIR/bin/activate" ]; then
  # shellcheck disable=SC1090
  source "$VENV_DIR/bin/activate"
fi

mkdir -p "$(dirname "$OUTPUT_PREFIX")"

python "$RWKV_PEFT_DIR/json2binidx_tool/tools/preprocess_data.py" \
  --input "$INPUT_JSONL" \
  --output-prefix "$OUTPUT_PREFIX" \
  --vocab-file "$TOKENIZER_FILE" \
  --dataset-impl mmap \
  --tokenizer-type RWKVTokenizer \
  --append-eod \
  --workers "$WORKERS"

echo
echo "Done."
echo "Use this data prefix in train scripts:"
echo "  ${OUTPUT_PREFIX}_text_document"

