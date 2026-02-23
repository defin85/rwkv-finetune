# Change: Рефакторинг оркестрации обучения на Apache Airflow

## Why
Текущий pipeline обучения (`prepare_binidx -> train -> eval/release`) запускается через локальные скрипты и остаётся в значительной степени ручным. Это повышает операционный риск: сложнее повторять прогоны, контролировать статусы стадий и управлять retry/failure-поведением.

Принято решение сделать Apache Airflow основным orchestration-путём вместо `refactor-mlops-lite-workflow`: heavy-orchestration подход с DAG-управлением формализует execution lifecycle и снижает операционную хрупкость.

## What Changes
- Добавляется новая capability `airflow-orchestration` для управления обучающим pipeline через Apache Airflow DAG.
- Фиксируется Airflow-first контракт стадий (`prepare`, `train`, `evaluate`, `release`) и их зависимостей в DAG.
- Фиксируется модель интеграции с существующими shell wrappers (`scripts/prepare_binidx.sh`, `scripts/train.sh`, `scripts/train_*.sh`) без переписывания внутренних алгоритмов обучения.
- Добавляются требования к orchestration-политикам: retries, fail-fast, audit trail, и сериализация GPU-heavy задач.
- Фиксируется primary-policy оркестрации: deployment MUST использовать `airflow` как основной runtime; `mlops-lite` не должен активироваться как primary path.

## Impact
- Affected specs: `airflow-orchestration` (new capability).
- Связанные изменения: `refactor-mlops-lite-workflow` архивирован как неактуальный; используются quality/eval policy из `add-1c-dataset-strategy`.
- Affected code (на этапе apply): новая структура Airflow (`dags/`, `plugins/`, `orchestration config`), адаптация entrypoint-скриптов, обновления `README.md` и `AGENTS.md`.
- Breaking impact: primary operational path закрепляется за Airflow DAG trigger (вместо ручного shell-run), при сохранении совместимости базовых train-скриптов как исполняемых unit-операций.
