#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

CONFIG_ROOT="$TMP_DIR/config_export"
SYNTAX_JSONL="$TMP_DIR/syntax.jsonl"
KB_JSONL="$TMP_DIR/kb.jsonl"
MANIFEST_JSON="$TMP_DIR/multisource.manifest.json"
ONEC_CORE_JSONL="$TMP_DIR/onec_core.jsonl"
CORE_REPORT_JSON="$TMP_DIR/onec_core.report.json"
CODING_JSONL="$TMP_DIR/coding.jsonl"
RU_JSONL="$TMP_DIR/ru.jsonl"
TRAIN_TEXT="$TMP_DIR/release.txt"
PROFILE_REPORT_JSON="$TMP_DIR/release.report.json"
OUTPUT_PREFIX="$TMP_DIR/processed/multisource_smoke"
DATA_PREFIX="${OUTPUT_PREFIX}_text_document"

mkdir -p "$CONFIG_ROOT/CommonModules" "$CONFIG_ROOT/Catalogs/Nomenclature" "$CONFIG_ROOT/Documents/Order"

printf '%s\n' \
  'Процедура ОбщаяПроцедура()' \
  '    Сообщить("common");' \
  'КонецПроцедуры' \
  > "$CONFIG_ROOT/CommonModules/CommonModule.bsl"

printf '%s\n' \
  'Функция ПолучитьМенеджер()' \
  '    Возврат Истина;' \
  'КонецФункции' \
  > "$CONFIG_ROOT/Catalogs/Nomenclature/ManagerModule.bsl"

printf '%s\n' \
  'Процедура ПровестиДокумент()' \
  '    Сообщить("object");' \
  'КонецПроцедуры' \
  > "$CONFIG_ROOT/Documents/Order/ObjectModule.bsl"

printf '%s\n' \
  '{"title":"Новый Запрос","description":"Создаёт объект запроса 1С.","syntax":"Запрос = Новый Запрос;","example":"Запрос = Новый Запрос;\nЗапрос.Текст = \"ВЫБРАТЬ 1\";"}' \
  '{"title":"НайтиСтроки","description":"Возвращает подходящие строки таблицы значений.","syntax":"Таблица.НайтиСтроки(СтруктураОтбора)"}' \
  > "$SYNTAX_JSONL"

printf '%s\n' \
  '{"title":"Работа с документами","content":"Документы 1С поддерживают проведение и запись.","origin_ref":"https://kb.1ci.com/example/documents"}' \
  > "$KB_JSONL"

cat > "$MANIFEST_JSON" <<EOF
{
  "dataset_name": "onec-multisource-core-smoke",
  "dataset_version": "v0",
  "sources": {
    "config_export": {
      "path": "$CONFIG_ROOT",
      "source": "smoke-config-export",
      "license": "internal",
      "origin_ref": "local://smoke/config-export",
      "contour": "core"
    },
    "syntax_helper_export": {
      "path": "$SYNTAX_JSONL",
      "source": "smoke-syntax-helper",
      "license": "internal",
      "origin_ref": "local://smoke/syntax-helper-export",
      "contour": "core"
    },
    "kb1c_snapshot": {
      "path": "$KB_JSONL",
      "source": "kb.1ci.com",
      "license": "open",
      "origin_ref": "https://kb.1ci.com/smoke-snapshot",
      "contour": "core"
    }
  }
}
EOF

python "$ROOT_DIR/scripts/build_1c_multisource_core_corpus.py" \
  --assembly-manifest "$MANIFEST_JSON" \
  --output-jsonl "$ONEC_CORE_JSONL" \
  --report-output "$CORE_REPORT_JSON" \
  --hard-min-mb 0 \
  --target-max-mb 1

printf '%s\n' \
  '{"user_prompt":"Напиши функцию C1","assistant_response":"def c1():\n    return '\''c1'\''","metadata":{"source":"smoke-test","license":"internal","origin_ref":"local://smoke/c1","contour":"extended","segment":"coding_general","split":"train","quality_rationale":"Synthetic coding fixture for builder validation."}}' \
  '{"user_prompt":"Напиши функцию C2","assistant_response":"def c2():\n    return '\''c2'\''","metadata":{"source":"smoke-test","license":"internal","origin_ref":"local://smoke/c2","contour":"extended","segment":"coding_general","split":"train","quality_rationale":"Synthetic coding fixture for builder validation."}}' \
  > "$CODING_JSONL"

printf '%s\n' \
  '{"user_prompt":"Объясни RUS1","assistant_response":"Это ответ ANS1","metadata":{"source":"smoke-test","license":"internal","origin_ref":"local://smoke/rus1","contour":"extended","segment":"ru_identity","split":"train","quality_rationale":"Synthetic RU fixture for builder validation."}}' \
  '{"user_prompt":"Объясни RUS2","assistant_response":"Это ответ ANS2","metadata":{"source":"smoke-test","license":"internal","origin_ref":"local://smoke/rus2","contour":"extended","segment":"ru_identity","split":"train","quality_rationale":"Synthetic RU fixture for builder validation."}}' \
  > "$RU_JSONL"

python "$ROOT_DIR/scripts/build_1c_expert_v4_dataset.py" \
  --profile "$ROOT_DIR/configs/dataset/1c-expert-v4.profile.json" \
  --onec-core-jsonl "$ONEC_CORE_JSONL" \
  --coding-jsonl "$CODING_JSONL" \
  --ru-jsonl "$RU_JSONL" \
  --output-text "$TRAIN_TEXT" \
  --report-output "$PROFILE_REPORT_JSON" \
  --hard-min-mb 0

"$ROOT_DIR/scripts/prepare_binidx.sh" "$TRAIN_TEXT" "$OUTPUT_PREFIX"

if [ ! -f "${DATA_PREFIX}.bin" ] || [ ! -f "${DATA_PREFIX}.idx" ]; then
  echo "Smoke failed: missing binidx artifacts for prefix ${DATA_PREFIX}" >&2
  exit 1
fi

echo "Smoke passed."
echo "Onec core JSONL: $ONEC_CORE_JSONL"
echo "Core report: $CORE_REPORT_JSON"
echo "Train text: $TRAIN_TEXT"
echo "Profile report: $PROFILE_REPORT_JSON"
echo "Data prefix: $DATA_PREFIX"
