# Change: Рефакторинг проекта под MLOps-lite для обучения RWKV v7

## Статус
Неактуально с 23 февраля 2026: выбран путь `refactor-orchestration-to-airflow`, где Apache Airflow принят как основной orchestration profile.

## Why
Текущий pipeline уже рабочий (`bootstrap -> prepare_binidx -> train`), но остаётся «операционно хрупким»: запуск зависит от ручных шагов, а воспроизводимость и трассировка артефактов не формализованы в едином контракте.

Для регулярного дообучения под 1C:Enterprise нужен MLOps-lite подход: минимальная оркестрация, формальные стадии, строгая связка `dataset release -> training run -> adapter release`, и блокирующие quality/eval gates перед релизом.

## What Changes
- Добавляется новая capability `mlops-lite-workflow` для локального file-based pipeline без внедрения тяжёлых orchestration frameworks.
- Вводится stage-контракт для `prepare`, `train`, `evaluate`, `release` с фиксированными входами/выходами и статусами выполнения.
- Вводится обязательный `run manifest` (snapshot конфигов, git revision, env/runtime параметры, ссылки на входные и выходные артефакты).
- Вводится lineage-модель артефактов: версия датасета -> training run -> версия адаптера.
- Вводятся release gates для адаптера: обязательный `domain eval` + `retention eval`, плюс проверка, что датасет прошёл quality gates.
- Фиксируется ограничение MLOps-lite: локальный запуск в WSL остаётся первым классом, внешние платформы трекинга/оркестрации не являются обязательными.

## Impact
- Affected specs: `mlops-lite-workflow` (new capability), связанный change: `add-1c-dataset-strategy` (`dataset-development`).
- Affected code (на этапе apply): `scripts/train.sh`, `scripts/prepare_binidx.sh`, обёртки `scripts/train_*.sh`, структура `runs/`, документация `README.md` и `AGENTS.md`.
- Breaking impact: прямых API-breaking изменений не планируется; допустимы изменения внутренней структуры run-артефактов при сохранении совместимости базовых CLI-аргументов.
