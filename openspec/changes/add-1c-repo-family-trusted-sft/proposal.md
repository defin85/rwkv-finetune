# Change: Добавить trusted SFT-сборку из локального 1C repo family и git history

## Why
В распоряжении команды есть локальные git-репозитории 1С с глубокой историей изменений, которые потенциально могут дать сильный trusted-корпус для дообучения RWKV под 1C. При этом предварительный анализ показывает, что отдельные репозитории могут представлять один и тот же source family с почти полным перекрытием текущего snapshot-состояния.

Без формального контракта на такой источник остаются риски:
- переоценка объёма trusted-корпуса из-за дубликатов между sibling-репозиториями;
- leakage между train/dev/eval при разбиении "по репозиториям", хотя фактически это одна и та же конфигурация;
- смешение truly trusted sample с synthetic/AI-enriched sample в одном контуре;
- отсутствие честного отчёта о фактически достигнутом объёме после dedup.

## What Changes
- Добавляется capability сборки trusted SFT-корпуса из локального 1C `repo family` с явным `source_family_id`.
- Фиксируется входной manifest для локального source family:
  - список корней репозиториев;
  - canonical snapshot root;
  - usage/training permission;
  - provenance/license поля.
- Фиксируются детерминированные trusted sample-классы первого релиза:
  - snapshot-derived sample из текущих BSL-модулей;
  - history-derived sample из локализуемых git-изменений в BSL;
  - metadata-linked context из локальных `conf_files`, если он извлекается без LLM-обогащения.
- Фиксируется, что `.epf`-связанные BSL-модули не входят в trusted contour v1.
- Фиксируются правила overlap detection и канонизации между sibling-репозиториями одного source family до расчёта объёма.
- Фиксируется historical split policy: sibling-репозитории одного family MUST NOT считаться независимыми границами train/dev/eval.
- Фиксируется baseline split policy первого релиза: temporal/lineage split + near-dedup обязателен, отдельный holdout по task families не требуется.
- Фиксируется честный volume policy: trusted release MUST считать только уникальный объём после dedup, MUST удовлетворять обязательному hard minimum и MUST NOT добивать размер synthetic filler-данными.

## Impact
- Affected specs:
  - `dataset-source-ingestion`
  - `dataset-development`
- Related changes:
  - `add-1c-dataset-strategy` (двухконтурная стратегия, provenance, split и quality gates);
  - `add-1c-multisource-corpus-assembly` (общий ingest трёх 1C-источников);
  - `add-1c-expert-v4-dataset-profile` (профиль релизной сборки и mix).
- Affected code:
  - новые/обновлённые source adapters для локального repo family и git history;
  - отчётность release-manifest/release-report по overlap, unique volume и split lineage;
  - документация по intake локальных 1C-репозиториев в trusted-контур.
