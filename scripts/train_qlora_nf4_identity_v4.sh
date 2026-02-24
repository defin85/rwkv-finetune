#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

exec "$ROOT_DIR/scripts/train.sh" \
  --model "$ROOT_DIR/configs/model/rwkv7-7.2b.env" \
  --profile "$ROOT_DIR/configs/profile/qlora-nf4-identity-v4.env" \
  "$@"
