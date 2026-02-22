#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

exec "$ROOT_DIR/scripts/train.sh" \
  --model "$ROOT_DIR/configs/model/rwkv7-1.5b.env" \
  --profile "$ROOT_DIR/configs/profile/qlora-int8.env" \
  "$@"

