## Context
Неактуально с 23 февраля 2026: данный дизайн отменён, поскольку принят `refactor-orchestration-to-airflow` с Apache Airflow как primary orchestration profile.

Проект использует thin-wrapper shell архитектуру и локальный стек (WSL, без Docker/K8s). Сейчас есть рабочие точки входа для bootstrap, подготовки binidx и обучения, но нет формального runtime lifecycle для регулярных релизов адаптеров.

В параллельном change `add-1c-dataset-strategy` уже зафиксированы правила качества датасета и антидеградации. Этому change нужен операционный слой: как запускать train/eval/release воспроизводимо и проверяемо.

## Goals / Non-Goals
- Goals:
  - Ввести MLOps-lite контракт для локального pipeline с явными стадиями и проверками.
  - Сделать каждый запуск воспроизводимым через manifest и snapshot конфигурации.
  - Обеспечить сквозную трассировку lineage между датасетом, run и адаптером.
  - Блокировать выпуск адаптера при провале quality/eval gates.
- Non-Goals:
  - Не внедрять полнофункциональные orchestration платформы (Airflow/Prefect/Kubeflow) в v1.
  - Не делать обязательным внешний tracking server (MLflow/W&B self-hosted).
  - Не переписывать внутренности `RWKV-PEFT`.

## Decisions
- Decision: Использовать file-based orchestration поверх текущих скриптов.
  - Why: соответствует ограничению «WSL + no Docker», минимальный операционный overhead.
  - Alternative: Airflow/Prefect/Kubeflow.
  - Why not now: избыточная сложность для одного локального training pipeline.

- Decision: Зафиксировать stage model `prepare -> train -> evaluate -> release`.
  - Why: единый контракт входов/выходов и детерминированные точки fail-fast.
  - Alternative: свободные ad-hoc команды.
  - Why not now: ad-hoc не даёт воспроизводимости и аудита.

- Decision: Ввести immutable `run manifest` как источник истины.
  - Why: обеспечивает воспроизводимость и расследование регрессий.
  - Minimal manifest fields:
    - `run_id`, `created_at`, `status`;
    - `dataset_version`, `dataset_manifest_ref`;
    - `model_config_ref`, `profile_config_ref`, `resolved_config_snapshot`;
    - `git_commit`, `workspace_dirty`, `python_version`, `cuda_info`;
    - `train_command`, `artifacts` (checkpoints/logs/metrics), `eval_summary_ref`;
    - `release_decision` и причины блокировки/допуска.

- Decision: Ввести release gate для адаптера как обязательный policy step.
  - Why: нужен предсказуемый контроль деградации.
  - Gate contract:
    - dataset quality gates = PASS (из capability `dataset-development`);
    - domain eval = PASS;
    - retention eval = PASS;
    - регрессия retention относительно baseline не выходит за зафиксированный порог.

- Decision: Фиксировать lineage в файловых manifest-артефактах.
  - Why: простой и надёжный аудит без внешней БД.
  - Alternative: централизованный metadata store.
  - Why not now: не нужен для MLOps-lite старта.

## Pipeline Contract (v1)
- `prepare`:
  - Input: versioned dataset release (`train.jsonl` + dataset manifest).
  - Output: binidx prefix + checksum metadata.
- `train`:
  - Input: resolved configs + base model + binidx prefix.
  - Output: run directory с checkpoint-ами, логами и run manifest.
- `evaluate`:
  - Input: adapter checkpoint + eval suites (domain/retention).
  - Output: `eval_summary` с метриками и verdict.
- `release`:
  - Input: run manifest + eval summary + gate results.
  - Output: adapter release manifest или блокировка релиза с причинами.

## Risks / Trade-offs
- Риск: рост бюрократии запусков.
  - Mitigation: минимальный обязательный набор метаданных и автоматическая генерация manifest.
- Риск: частичная дисциплина при ручных запусках.
  - Mitigation: fail-fast проверки и запрет release без полного набора артефактов.
- Риск: пересечение ответственности с `add-1c-dataset-strategy`.
  - Mitigation: разделить зоны: `dataset-development` отвечает за качество данных, `mlops-lite-workflow` за runtime orchestration и release flow.

## Migration Plan
1. Зафиксировать новую capability в OpenSpec (этот change).
2. На этапе apply ввести структуру run/eval/release manifest и унифицированный stage runner.
3. Подключить gate-проверки и блокировку релиза.
4. Обновить README/AGENTS и провести smoke-run на коротком профиле.
5. Оставить внешние оркестраторы как опциональное расширение следующей итерации.

## Open Questions
- Нужен ли в v1 жёсткий запрет release при `workspace_dirty=true`, или достаточно предупреждения в manifest?
- Достаточно ли одного агрегированного retention-score для gate, или требуется минимум по подкатегориям уже в v1?
