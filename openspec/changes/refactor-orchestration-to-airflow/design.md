## Context
Проект уже имеет стабильные shell-этапы подготовки и обучения, но orchestration-поведение не централизовано: порядок действий, retry и контроль зависимостей поддерживаются вручную.

Пользовательский запрос: зафиксировать Apache Airflow как основной orchestration-путь. `refactor-mlops-lite-workflow` признан неактуальным и архивирован.

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
  - Зафиксировать Airflow как единственный primary orchestration profile и отклонять `mlops-lite` как primary runtime.
- Non-Goals:
  - Не переносить вычисления в Kubernetes на первом этапе.
  - Не заменять RWKV-PEFT internals.
  - Не делать обязательной внешнюю distributed очередь (Celery/RabbitMQ) в v1.

## Decisions
- Decision: Apache Airflow используется как primary scheduler/orchestrator проекта.
  - Why: зрелый DAG runtime, явные зависимости задач, retries и наблюдаемость.
  - Alternative: оставить file-based orchestration и ручной shell-run.
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

- Decision: Primary profile enforcement.
  - Why: `refactor-mlops-lite-workflow` архивирован как неактуальный; primary-runtime должен быть однозначным.
  - Policy: deployment MUST задавать `airflow` как primary path. Попытки активировать `mlops-lite` как primary path MUST отклоняться.

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
- Риск: документационный дрейф после смены решения с MLOps-lite на Airflow.
  - Mitigation: явная фиксация статуса архивирования MLOps-lite change и Airflow-first policy в спеках и документации.

## Migration Plan
1. Зафиксировать capability `airflow-orchestration` в OpenSpec (этот change).
2. Зафиксировать отказ от MLOps-lite пути: `refactor-mlops-lite-workflow` архивирован как неактуальный (23 февраля 2026).
3. На этапе apply добавить Airflow-структуру (`dags`, конфиг, bootstrap/runbook).
4. Реализовать DAG, который вызывает существующие `scripts/*.sh` и фиксирует статусы.
5. Включить blocking release-gates и контроль GPU concurrency.
6. Провести smoke-run DAG на коротком профиле и обновить docs.

## Open Questions
- Требуется ли в v1 расписание по cron, или достаточно manual trigger + backfill?
- Нужен ли отдельный Airflow DAG для retrain-on-new-dataset, или один унифицированный DAG для всех запусков?
