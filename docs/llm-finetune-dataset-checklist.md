# Чеклист подготовки датасета для fine-tuning LLM (под rwkv-finetune)

Дата обновления: 2026-02-24.

## 1) Цель датасета (до начала)

- [ ] Зафиксирована измеримая цель: что именно улучшаем (например, `identity` или `1C code generation`).
- [ ] Есть отдельный eval-набор под ту же цель (`domain eval`) и отдельный набор на удержание общих навыков (`retention eval`).
- [ ] Определён baseline (до обучения), чтобы сравнение было честным.

## 2) Источники и legal/provenance

- [ ] У каждого образца есть provenance: источник, лицензия, origin ref/ссылка.
- [ ] Данные без подтверждённой лицензии не попадают в релизный train-set.
- [ ] Секреты/PII удалены до формирования финального JSONL.

Рекомендуемый минимальный manifest-профиль на датасет:
- `dataset_version`
- `created_at`
- `source_summary`
- `license_summary`
- `sampling_policy`
- `dedup_policy`
- `split_policy`

## 3) Формат данных

Канонический формат sample для lifecycle-слоя:

```json
{
  "user_prompt": "<русский prompt>",
  "assistant_response": "<answer>",
  "metadata": {
    "source": "<source-id>",
    "license": "<license>",
    "origin_ref": "<origin-ref>",
    "contour": "core|extended",
    "segment": "<segment>",
    "split": "train|dev|eval"
  }
}
```

Derived compatibility-формат для текущих consumer'ов токенизации:

```json
{"text":"User: <prompt>\nAssistant: <answer>"}
```

- [ ] Каждая строка JSONL валидна (один JSON-объект на строку).
- [ ] Каноническая запись содержит `user_prompt` / `assistant_response` / `metadata`.
- [ ] Если используется derived `text`, он синхронизирован с канонической парой.
- [ ] Формат prompt/inference совпадает (не смешивать разные chat templates в одном train).
- [ ] `metadata.contour` принимает только `core` или `extended`.
- [ ] `metadata.source`, `metadata.license`, `metadata.origin_ref` не пустые и не используют placeholder `unknown`.

## 4) Баланс и состав выборки

Стартовый baseline для этого репозитория:

- генерация кода: 35%
- рефакторинг: 35%
- запросы 1C: 15%
- объяснение/ревью: 15%

Ограничения:
- [ ] Допуск по каждой категории не более ±5 п.п.
- [ ] Генерация и рефакторинг в паритете (в пределах допуска).
- [ ] Replay/mix-in общих данных (RU general + не-1C coding): 15-25%.

## 5) Антидеградация (catastrophic forgetting)

- [ ] Adapter-first режим (`LoRA/QLoRA`), базовые веса не изменяются.
- [ ] Без merge адаптера в базу по умолчанию.
- [ ] Низкий LR, умеренное число эпох, ранняя остановка при признаках overfitting.
- [ ] Проверка `retention eval` обязательна перед релизом.

## 6) Quality gates до запуска train

Встроенный скрипт:

```bash
python scripts/check_dataset_quality.py \
  --input data/raw/identity_hotfix_v4.jsonl \
  --output data/raw/identity_hotfix_v4.manifest.json \
  --strict
```

Базовые пороги (из текущего скрипта):

- `min_rows=200`
- `min_unique_ratio=0.95`
- `min_user_assistant_ratio=0.99`
- `min_identity_ratio=0.25` (для identity-набора)
- `max_top1_share=0.05`
- `max_qwen_negative_rows=0`
- `max_identity_brand_leak_rows=0`
- `max_transcript_leak_rows=0`

- [ ] `quality_status = PASS`
- [ ] Нет критических причин в `quality_reasons`

Для canonical release manifest:

```bash
python scripts/validate_dataset_release.py \
  --train /path/to/train.jsonl \
  --eval /path/to/eval.jsonl \
  --manifest-output data/curated/example.manifest.json \
  --dataset-name example \
  --dataset-version v0
```

- [ ] В manifest есть `source_summary`, `license_summary`, `sampling_policy`, `dedup_policy`, `split_policy`.
- [ ] `created_at_policy.source` отражает deterministic source timestamp policy или явный override.
- [ ] Train/Eval leakage = `0` по exact и near hash.
- [ ] Для 1C sample нет BSL diagnostics-level нарушений на release gate.
- [ ] Parser-level BSL validation отслеживается отдельно как future TODO `rwkv-finetune-v8q.3` и до интеграции `bsl-gradual-types` не считается реализованной.

Для repo/time split с отдельными eval bucket'ами:

```bash
python scripts/split_dataset_release.py \
  --input /path/to/canonical.jsonl \
  --train-output data/interim/example_train.jsonl \
  --eval-output data/interim/example_eval.jsonl \
  --eval-generation-output data/interim/example_eval_generation.jsonl \
  --eval-refactoring-output data/interim/example_eval_refactoring.jsonl \
  --manifest-output data/curated/example.manifest.json \
  --dataset-name example \
  --dataset-version v0 \
  --repo-key source_family_id \
  --repo-key origin_ref \
  --time-key commit_timestamp \
  --time-key created_at
```

- [ ] Для `eval_generation` есть только `code_generation`.
- [ ] Для `eval_refactoring` есть только `refactoring`.
- [ ] В `split_policy` зафиксированы repo/time keys и dedicated eval split contract.

## 7) Leakage и split-политика

- [ ] Train/Eval разнесены по времени/источнику или по документам (а не случайно построчно из одного параграфа).
- [ ] Выполнен exact dedup и near dedup (минимум на уровне train-train и train-eval).
- [ ] Eval не содержит ответов/перефразов из train (проверка near-dup обязательна).

## 8) Воспроизводимость

- [ ] Фиксирован seed в генераторе датасета.
- [ ] Зафиксированы версии скриптов/конфигов и sha256 датасета.
- [ ] Для каждого прогона уникальные `run_name`/`run_id`.
- [ ] Версия датасета удовлетворяет шаблону `vN` или `vN.M`.
- [ ] Используются stage directories `data/raw`, `data/interim`, `data/curated`.
- [ ] Для релиза сохранён `v0 report` с составом датасета, quality gates, eval verdicts и hard-case backlog.

Команда сборки `v0 report`:

```bash
python scripts/build_dataset_v0_report.py \
  --manifest data/curated/example.manifest.json \
  --eval-summary runs/example/eval_summary.json \
  --output-md docs/reports/example-v0-report.md \
  --output-json docs/reports/example-v0-report.json
```

- [ ] `eval_summary.json` содержит `domain_eval.categories`, `retention_eval.categories` и `hard_cases`.
- [ ] `scripts/produce_eval_artifacts.py` генерирует category artifacts и `hard_cases` из реальных `domain_eval_jsonl` / `retention_eval_jsonl`.
- [ ] `scripts/evaluate_adapter.sh` собирает summary из machine-readable runtime artifacts, а не только из verdict flags.

Для `scripts/build_1c_expert_v4_dataset.py`:
- [ ] `bsl-root` передаёт явный provenance contract через `--bsl-source/--bsl-license/--bsl-origin-ref/--bsl-contour`.
- [ ] `coding-jsonl` и `ru-jsonl` проходят lifecycle validation до profile serialization.
- [ ] Builder блокируется на non-RU prompt или невалидном provenance metadata для всех сегментов, включая `onec_bsl`.

Команда генерации identity-набора:

```bash
python scripts/build_identity_hotfix_dataset.py \
  --train-output data/raw/identity_hotfix_v4.jsonl \
  --eval-output data/raw/identity_hotfix_v4_eval.jsonl \
  --manifest-output data/raw/identity_hotfix_v4.manifest.json \
  --dataset-name identity_hotfix_v4
```

## 9) Запуск через Airflow

CLI-триггер с конфигом:

```bash
./scripts/run_pipeline.sh \
  --run-id identity-hotfix-v4-001 \
  --conf-file /home/egor/code/rwkv-finetune/configs/airflow/identity_hotfix_v4.conf.json
```

Перед запуском:
- [ ] `ORCHESTRATION_PROFILE=airflow`
- [ ] Валидный `input_jsonl`
- [ ] Валидный `dataset_manifest`
- [ ] Правильный `train_wrapper`
- [ ] Базовый `.pth` существует и указан в `load_model`
- [ ] `eval_model_path` указывает на inference-ready checkpoint для eval шага текущего run.
- [ ] Указаны отдельные `domain_eval_jsonl` и `retention_eval_jsonl`.
- [ ] Если используется не штатный inference path, задан `eval_inference_script`.

## 10) Критерии приёмки обучения

- [ ] Domain метрики улучшились относительно baseline.
- [ ] Retention не хуже guardrail (рекомендация: не хуже `-3%` агрегированно).
- [ ] Нет циклов/развала формата на smoke-промптах.
- [ ] Артефакты run содержат gate/eval/release manifests.

## 11) 1C-Expert-v4 профиль (операционный)

Профиль:
- `configs/dataset/1c-expert-v4.profile.json`

Сборка train-текста:

```bash
python scripts/build_1c_expert_v4_dataset.py \
  --profile configs/dataset/1c-expert-v4.profile.json \
  --bsl-root /path/to/onec/configuration \
  --bsl-source local-bsl-tree \
  --bsl-license internal \
  --bsl-origin-ref local://onec/configuration \
  --bsl-contour core \
  --coding-jsonl /path/to/coding.jsonl \
  --ru-jsonl /path/to/ru_identity.jsonl \
  --output-text data/raw/1c_expert_v4_train.txt \
  --report-output data/raw/1c_expert_v4.release.report.json
```

Для `coding_jsonl` / `ru_jsonl`:
- baseline external sources должны совпадать с allowlist профиля;
- если `metadata.source` не входит в allowlist для своего сегмента, row MUST содержать непустой `metadata.quality_rationale`, иначе builder завершится fail-closed.

Обязательные gate-проверки профиля:
- [ ] mix `50/30/20` по сегментам (`onec_bsl/coding_general/ru_identity`) в допуске ±5 п.п.
- [ ] покрытие модулей 1C: `common`, `manager`, `object`.
- [ ] в каждом sample есть `Instruction:` + `Response:` + `<|endoftext|>`.
- [ ] нет сырых JSON-объектов в train-text.
- [ ] release-report фиксирует actual mix и shuffle metadata.
- [ ] размер train-text не ниже `200 MB` (или явно заданного override для тестового режима).

Smoke-проверка:

```bash
./scripts/smoke_1c_expert_v4.sh
```

## 12) Trusted local repo-family (1C)

Если источник собирается из нескольких локальных git-репозиториев одной конфигурации:

- [ ] Есть `repo_family_manifest` с `source_family_id`, `repo_roots[]`, `canonical_snapshot_root`, `training_permission`, `usage_policy`, `license`, `origin_ref`.
- [ ] sibling-репозитории рассматриваются как один `source family`, а не как независимые train/eval boundary.
- [ ] trusted `v1` intake для repo-family ограничен BSL snapshot/history surface.
- [ ] Выполнена snapshot canonicalization и зафиксированы `identical_overlap_paths` / `conflict_paths`.
- [ ] `.epf`-связанные BSL-модули исключены из trusted `v1`.
- [ ] История git используется только для локализуемых BSL-изменений; широкие коммиты пропускаются с явной причиной.
- [ ] `dev/eval` формируются из поздних lineage changes; train очищен от exact/near duplicates относительно holdout.
- [ ] release-report содержит `target_min_mb`, `attained_unique_volume_mb` и `deficit_to_target_min_mb`.
- [ ] `attained_unique_volume_mb` не ниже обязательного hard minimum, иначе релиз блокируется.

Команда сборки:

```bash
python scripts/build_repo_family_trusted_corpus.py \
  --profile configs/dataset/1c-expert-v4.profile.json \
  --family-manifest /path/to/repo-family.manifest.json \
  --train-output data/raw/repo_family_train.jsonl \
  --dev-output data/raw/repo_family_dev.jsonl \
  --eval-output data/raw/repo_family_eval.jsonl \
  --report-output data/raw/repo_family.release.report.json
```

---

## Быстрый anti-pattern список

- [ ] Не обучать на «сырой книге целиком» без переразметки в instruction pairs.
- [ ] Не дублировать сотни почти одинаковых ответов (получите переобучение и циклы).
- [ ] Не смешивать несовместимые chat templates.
- [ ] Не выпускать адаптер без retention-eval.

---

## Официальные мануалы (первичные источники)

### OpenAI
- Supervised fine-tuning: формат данных (JSONL/chat):
  - https://developers.openai.com/api/docs/guides/supervised-fine-tuning/#formatting-your-data
- Fine-tuning best practices:
  - https://developers.openai.com/api/docs/guides/fine-tuning-best-practices/
- Optimizing LLM accuracy (раздел про fine-tuning и датасеты):
  - https://developers.openai.com/api/docs/guides/optimizing-llm-accuracy/#fine-tuning

### Hugging Face
- Chat templating (критично для совместимости формата):
  - https://huggingface.co/docs/transformers/chat_templating
- TRL SFTTrainer:
  - https://huggingface.co/docs/trl/sft_trainer
- TRL dataset formats:
  - https://huggingface.co/docs/trl/dataset_formats

### Azure / Cloud
- Azure OpenAI fine-tuning:
  - https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/fine-tuning
- AWS Bedrock dataset preparation:
  - https://docs.aws.amazon.com/bedrock/latest/userguide/model-customization-prepare.html
- Google Vertex tuning data prep:
  - https://cloud.google.com/vertex-ai/generative-ai/docs/models/translation-supervised-tuning-prepare
