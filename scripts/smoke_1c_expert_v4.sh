#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

BSL_ROOT="$TMP_DIR/onec"
CODING_JSONL="$TMP_DIR/coding.jsonl"
RU_JSONL="$TMP_DIR/ru.jsonl"
TRAIN_TEXT="$TMP_DIR/release.txt"
REPORT_JSON="$TMP_DIR/release.report.json"
OUTPUT_PREFIX="$TMP_DIR/processed/smoke"
DATA_PREFIX="${OUTPUT_PREFIX}_text_document"

mkdir -p "$BSL_ROOT/CommonModules" "$BSL_ROOT/Catalogs/Nomenclature" "$BSL_ROOT/Documents/Order"

printf '%s\n' \
  'Процедура ОбщаяПроцедура()' \
  '    Сообщить("common");' \
  'КонецПроцедуры' \
  > "$BSL_ROOT/CommonModules/CommonModule.bsl"

printf '%s\n' \
  'Функция ПолучитьМенеджер()' \
  '    Возврат Истина;' \
  'КонецФункции' \
  > "$BSL_ROOT/Catalogs/Nomenclature/ManagerModule.bsl"

printf '%s\n' \
  'Процедура ПровестиДокумент()' \
  '    Сообщить("object");' \
  'КонецПроцедуры' \
  > "$BSL_ROOT/Documents/Order/ObjectModule.bsl"

printf '%s\n' \
  '{"user_prompt":"Напиши функцию C1","assistant_response":"def c1():\n    return '\''c1'\''","metadata":{"source":"smoke-test","license":"internal","origin_ref":"local://smoke/c1","contour":"extended","segment":"coding_general","split":"train"}}' \
  '{"user_prompt":"Напиши функцию C2","assistant_response":"def c2():\n    return '\''c2'\''","metadata":{"source":"smoke-test","license":"internal","origin_ref":"local://smoke/c2","contour":"extended","segment":"coding_general","split":"train"}}' \
  > "$CODING_JSONL"

printf '%s\n' \
  '{"user_prompt":"Объясни RUS1","assistant_response":"Это ответ ANS1","metadata":{"source":"smoke-test","license":"internal","origin_ref":"local://smoke/rus1","contour":"extended","segment":"ru_identity","split":"train"}}' \
  '{"user_prompt":"Объясни RUS2","assistant_response":"Это ответ ANS2","metadata":{"source":"smoke-test","license":"internal","origin_ref":"local://smoke/rus2","contour":"extended","segment":"ru_identity","split":"train"}}' \
  > "$RU_JSONL"

python "$ROOT_DIR/scripts/build_1c_expert_v4_dataset.py" \
  --profile "$ROOT_DIR/configs/dataset/1c-expert-v4.profile.json" \
  --bsl-root "$BSL_ROOT" \
  --bsl-source "smoke-test-bsl" \
  --bsl-license "internal" \
  --bsl-origin-ref "local://smoke/onec" \
  --bsl-contour "core" \
  --coding-jsonl "$CODING_JSONL" \
  --ru-jsonl "$RU_JSONL" \
  --output-text "$TRAIN_TEXT" \
  --report-output "$REPORT_JSON" \
  --hard-min-mb 0

"$ROOT_DIR/scripts/prepare_binidx.sh" "$TRAIN_TEXT" "$OUTPUT_PREFIX"

if [ ! -f "${DATA_PREFIX}.bin" ] || [ ! -f "${DATA_PREFIX}.idx" ]; then
  echo "Smoke failed: missing binidx artifacts for prefix ${DATA_PREFIX}" >&2
  exit 1
fi

echo "Smoke passed."
echo "Train text: $TRAIN_TEXT"
echo "Report: $REPORT_JSON"
echo "Data prefix: $DATA_PREFIX"
