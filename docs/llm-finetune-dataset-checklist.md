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

Для текущего pipeline репозитория канонический формат строки:

```json
{"text":"User: <prompt>\nAssistant: <answer>"}
```

- [ ] Каждая строка JSONL валидна (один JSON-объект на строку).
- [ ] Внутри `text` строго один `User:` и один `Assistant:`.
- [ ] Формат prompt/inference совпадает (не смешивать разные chat templates в одном train).

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
  --input data/raw/identity_hotfix_v3.jsonl \
  --output data/raw/identity_hotfix_v3.manifest.json \
  --strict
```

Базовые пороги (из текущего скрипта):

- `min_rows=200`
- `min_unique_ratio=0.95`
- `min_user_assistant_ratio=0.99`
- `min_identity_ratio=0.25` (для identity-набора)
- `max_top1_share=0.05`
- `max_qwen_negative_rows=0`

- [ ] `quality_status = PASS`
- [ ] Нет критических причин в `quality_reasons`

## 7) Leakage и split-политика

- [ ] Train/Eval разнесены по времени/источнику или по документам (а не случайно построчно из одного параграфа).
- [ ] Выполнен exact dedup и near dedup (минимум на уровне train-train и train-eval).
- [ ] Eval не содержит ответов/перефразов из train (проверка near-dup обязательна).

## 8) Воспроизводимость

- [ ] Фиксирован seed в генераторе датасета.
- [ ] Зафиксированы версии скриптов/конфигов и sha256 датасета.
- [ ] Для каждого прогона уникальные `run_name`/`run_id`.

Команда генерации identity-набора:

```bash
python scripts/build_identity_hotfix_dataset.py \
  --train-output data/raw/identity_hotfix_v3.jsonl \
  --eval-output data/raw/identity_hotfix_v3_eval.jsonl \
  --manifest-output data/raw/identity_hotfix_v3.manifest.json
```

## 9) Запуск через Airflow

CLI-триггер с конфигом:

```bash
./scripts/run_pipeline.sh \
  --run-id identity-hotfix-v3-001 \
  --conf-file /home/egor/code/rwkv-finetune/configs/airflow/identity_hotfix_v3.conf.json
```

Перед запуском:
- [ ] `ORCHESTRATION_PROFILE=airflow`
- [ ] Валидный `input_jsonl`
- [ ] Валидный `dataset_manifest`
- [ ] Правильный `train_wrapper`
- [ ] Базовый `.pth` существует и указан в `load_model`

## 10) Критерии приёмки обучения

- [ ] Domain метрики улучшились относительно baseline.
- [ ] Retention не хуже guardrail (рекомендация: не хуже `-3%` агрегированно).
- [ ] Нет циклов/развала формата на smoke-промптах.
- [ ] Артефакты run содержат gate/eval/release manifests.

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

