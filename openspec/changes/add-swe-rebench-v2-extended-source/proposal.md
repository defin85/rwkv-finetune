# Change: Добавить future-ingest SWE-rebench-V2 как derived external source для `coding_general`

## Why
Текущий профиль `1C-Expert-v4` допускает только базовый allowlist внешних non-1C источников для сегмента `coding_general`: `MagicCoder-Evol-Instruct-110K` и `CodeAlpaca-20k`. При этом `SWE-rebench-V2` даёт более сильный SWE-сигнал: реальные issue-based задачи, gold patch, test metadata, provenance по репозиторию и commit.

Сейчас пайплайн не готов принимать такой источник напрямую:
- текущий builder ожидает нормализованные `instruction/output` или `text`, а не SWE task instances;
- стратегическая политика требует русскоязычный `user_prompt`;
- внешний источник имеет mixed per-instance repo licenses и richer provenance, чем текущий coding allowlist;
- raw task rows легко перепутать с execution-runtime корпусом, хотя в этом репозитории пока нет execution-based train loop.

Без отдельного change остаются риски:
- прямой импорт английских `problem_statement` в train;
- потеря instance-level provenance и repo-license;
- обучение модели на сырых unified diff вместо нормализованного SFT target;
- преждевременное смешение task dataset и execution/runtime capability.

## What Changes
- Добавляется capability future-ingest `nebius/SWE-rebench-V2` как локально staged внешнего источника для derived SFT sample.
- Фиксируется, что `v1` охватывает только issue-based corpus `SWE-rebench-V2` и не включает `SWE-rebench-V2-PRs`.
- Фиксируется, что `SWE-rebench-V2` попадает только в контур `extended` и только в сегмент `coding_general`.
- Фиксируется обязательная нормализация в канонический sample-контракт:
  - `user_prompt` на русском языке;
  - `assistant_response` как derived fix-oriented SFT target;
  - оригинальный `problem_statement`, `patch`, `test_patch`, `FAIL_TO_PASS`, `PASS_TO_PASS`, `interface`, `meta` сохраняются в metadata/provenance.
- Фиксируются eligibility и quality gates для instance-level curating:
  - обязательные поля provenance и лицензии;
  - обязательный локальный snapshot/manifest;
  - fail-closed при неполной схеме или нарушении языковой политики.
- Фиксируется release cap первого релиза: `SWE-rebench-V2` MUST NOT занимать больше `50%` сегмента `coding_general`.

## Impact
- Affected specs:
  - `dataset-source-ingestion`
  - `dataset-development`
- Related changes:
  - `add-1c-dataset-strategy` (двухконтурная модель, RU-only prompts, quality gates);
  - `add-1c-expert-v4-dataset-profile` (allowlist и mix профиля `1C-Expert-v4`);
  - `add-1c-multisource-corpus-assembly` (не пересекается по `onec_bsl`, но задаёт общую дисциплину provenance).
- Affected code:
  - source adapter / normalizer для staged snapshot `SWE-rebench-V2`;
  - release manifest/report для translation provenance и instance-level filtering;
  - профильный allowlist и документация intake внешних SWE datasets.
