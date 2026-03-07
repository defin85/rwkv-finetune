# Change: Добавить reviewer-curated 1C pattern corpus из локального repo family

## Why
Текущий change `add-1c-repo-family-trusted-sft` даёт deterministic trusted baseline из snapshot/history локального repo family, но он намеренно не решает задачу semantic curation. Такой baseline полезен как `core` источник, однако он слишком грубый для обучения переносимым 1C-паттернам: модель видит в основном `метод -> код метода`, а не типовые инженерные практики, anti-patterns и обобщаемые решения.

Практическая цель следующего слоя другая:
- не учить модель конкретной конфигурации;
- открывать файлы и читать их как reviewer;
- вытаскивать переносимые 1C-паттерны, smell-и и refactoring opportunities;
- формировать из этого обучающие sample, полезные за пределами исходной конфигурации.

Без отдельного change остаются риски:
- смешение deterministic trusted extraction и reviewer-curated semantic curation в одном контуре;
- переобучение на конфигурационно-специфичных названиях и бизнес-логике;
- отсутствие workflow для пофайлового review при ограниченных token budgets;
- отсутствие quality gates на переносимость и traceability curated sample.

## What Changes
- Добавляется capability reviewer-curated сборки 1C pattern corpus из локального `repo family`.
- Фиксируется, что новый корпус относится к `extended` контуру и сегменту `onec_bsl`, а не к `core`.
- Фиксируется batch-oriented workflow:
  - `curation_batch_manifest` со списком файлов/модулей для review;
  - `coverage_report` по просмотренным файлам;
  - derived dataset release из reviewer-curated sample.
- Фиксируются допустимые sample-классы reviewer-curated корпуса:
  - `pattern_generation`
  - `pattern_refactor`
  - `pattern_review`
  - `pattern_explanation`
- Фиксируется обязательная generalization policy:
  - sample MUST выделять переносимый 1C-паттерн;
  - sample MUST минимизировать конфигурационно-специфичные сущности;
  - sample MUST сохранять provenance до файла/модуля и reviewer rationale.
- Фиксируется, что raw bulk extraction "один метод = один sample" не считается реализацией этого change.

## Impact
- Affected specs:
  - `dataset-source-ingestion`
  - `dataset-development`
- Related changes:
  - `add-1c-dataset-strategy` (двухконтурная модель и quality gates);
  - `add-1c-repo-family-trusted-sft` (deterministic baseline из того же source family);
  - `add-1c-expert-v4-dataset-profile` (размещение в `onec_bsl` сегменте).
- Affected code:
  - новые manifests/инструменты для review batches и coverage tracking;
  - curated dataset assembler/exporter;
  - документация reviewer workflow и criteria для pattern extraction.
