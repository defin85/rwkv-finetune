## Context
Проект уже имеет стабильные shell-этапы подготовки и обучения, но orchestration-поведение не централизовано: порядок действий, retry и контроль зависимостей поддерживаются вручную.

Пользовательский запрос: подготовить альтернативный вариант архитектуры (вместо `refactor-mlops-lite-workflow`) на Apache Airflow, чтобы затем выбрать один из подходов.

Ограничения проекта:
- локальный WSL-first контур;
- Docker не обязателен;
- обучение GPU-bound и обычно выполняется на одной машине;
- текущие скрипты и конфиги должны переиспользоваться, а не переписываться.

## Goals / Non-Goals
- Goals:
  - Ввести Apache Airflow как orchestrator для train lifecycle.
  - Сохранить существующие скрипты как исполняемые шаги DAG.
  - Добавить управляемые retries, статусы, журналирование и операционный audit trail.
  - Формализовать policy выбора orchestration-профиля как mutually exclusive режима с MLOps-lite вариантом.
- Non-Goals:
  - Не переносить вычисления в Kubernetes на первом этапе.
  - Не заменять RWKV-PEFT internals.
  - Не делать обязательной внешнюю distributed очередь (Celery/RabbitMQ) в v1.

## Decisions
- Decision: Apache Airflow используется как primary scheduler/orchestrator для этого варианта.
  - Why: зрелый DAG runtime, явные зависимости задач, retries и наблюдаемость.
  - Alternative: оставить file-based orchestration (`refactor-mlops-lite-workflow`).
  - Trade-off: выше инфраструктурная сложность, чем у MLOps-lite.

- Decision: Executor профиль для v1 — `LocalExecutor` с persistent metadata DB.
  - Why: достаточно для single-node WSL pipeline, сохраняет путь к масштабированию.
  - Alternative: `SequentialExecutor`.
  - Why not: слишком ограничивает параллелизм и устойчивость для orchestration-heavy сценариев.

- Decision: Task payload остаётся shell-first.
  - Why: минимизация риска регрессий; reuse проверенных `scripts/*.sh`.
  - Implementation intent: DAG tasks вызывают существующие wrappers и проверяют артефакты на выходе.

- Decision: GPU сериализация на уровне Airflow pools.
  - Why: предотвратить конкуренцию за одну GPU и нестабильные OOM/driver-failures.
  - Baseline: pool на training/eval задачи с ограничением concurrency `1`.

- Decision: Release gate в DAG является блокирующим.
  - Why: adapter release допускается только после PASS по domain/retention eval и quality status датасета.
  - Cross-capability link: правила качества данных берутся из `dataset-development`.

- Decision: Mutual exclusion orchestration profile.
  - Why: у пользователя два альтернативных архитектурных варианта; одновременный primary-runtime создаёт двусмысленность operational policy.
  - Policy: в deployment выбирается только один профиль (`mlops-lite` или `airflow`) как canonical execution path.

## DAG Contract (v1)
- `prepare_dataset`:
  - Input: versioned `train.jsonl` + dataset manifest.
  - Output: binidx prefix + preprocess status.
- `train_adapter`:
  - Input: base model, model/profile config, data prefix.
  - Output: run artifacts + checkpoint references.
- `evaluate_adapter`:
  - Input: produced adapter + eval suites.
  - Output: domain/retention metrics + verdict.
- `release_adapter`:
  - Input: train/eval outputs + gate status.
  - Output: adapter release manifest или блокировка релиза.

## Risks / Trade-offs
- Риск: инфраструктурная нагрузка (Airflow setup, metadata DB, service lifecycle).
  - Mitigation: минимальный installation profile и чёткий runbook.
- Риск: operational drift между Airflow DAG и shell-скриптами.
  - Mitigation: shell-first контракт и валидация входов/выходов каждой task.
- Риск: одновременное существование двух альтернативных changes может запутать implementation.
  - Mitigation: явная фиксация mutually exclusive статуса в спеках и документации.

## Migration Plan
1. Зафиксировать capability `airflow-orchestration` в OpenSpec (этот change).
2. На этапе apply добавить Airflow-структуру (`dags`, конфиг, bootstrap/runbook).
3. Реализовать DAG, который вызывает существующие `scripts/*.sh` и фиксирует статусы.
4. Включить blocking release-gates и контроль GPU concurrency.
5. Провести smoke-run DAG на коротком профиле и обновить docs.

## Open Questions
- Требуется ли в v1 расписание по cron, или достаточно manual trigger + backfill?
- Нужен ли отдельный Airflow DAG для retrain-on-new-dataset, или один унифицированный DAG для всех запусков?
