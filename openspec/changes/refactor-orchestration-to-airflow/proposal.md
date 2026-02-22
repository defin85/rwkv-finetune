# Change: Рефакторинг оркестрации обучения на Apache Airflow

## Why
Текущий pipeline обучения (`prepare_binidx -> train -> eval/release`) запускается через локальные скрипты и остаётся в значительной степени ручным. Это повышает операционный риск: сложнее повторять прогоны, контролировать статусы стадий и управлять retry/failure-поведением.

Нужен альтернативный вариант к `refactor-mlops-lite-workflow`: heavy-orchestration подход на Apache Airflow с DAG-управлением, чтобы формализовать execution lifecycle и снизить операционную хрупкость.

## What Changes
- Добавляется новая capability `airflow-orchestration` для управления обучающим pipeline через Apache Airflow DAG.
- Фиксируется Airflow-first контракт стадий (`prepare`, `train`, `evaluate`, `release`) и их зависимостей в DAG.
- Фиксируется модель интеграции с существующими shell wrappers (`scripts/prepare_binidx.sh`, `scripts/train.sh`, `scripts/train_*.sh`) без переписывания внутренних алгоритмов обучения.
- Добавляются требования к orchestration-политикам: retries, fail-fast, audit trail, и сериализация GPU-heavy задач.
- Фиксируется политика выбора варианта оркестрации: deployment MUST выбирать один вариант (`mlops-lite` или `airflow`), без одновременного включения обоих как primary runtime.

## Impact
- Affected specs: `airflow-orchestration` (new capability).
- Связанные изменения: альтернатива к `refactor-mlops-lite-workflow`; использует quality/eval policy из `add-1c-dataset-strategy`.
- Affected code (на этапе apply): новая структура Airflow (`dags/`, `plugins/`, `orchestration config`), адаптация entrypoint-скриптов, обновления `README.md` и `AGENTS.md`.
- Breaking impact: возможна смена primary operational path (ручной shell-run -> Airflow DAG trigger), при сохранении совместимости базовых train-скриптов как исполняемых unit-операций.
