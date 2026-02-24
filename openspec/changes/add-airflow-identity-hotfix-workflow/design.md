## Context
Текущий Airflow lifecycle ориентирован на общий train/eval/release контур и не содержит целевого gate для identity-регрессий (пример: ответ "я Qwen" вместо "RWKV-7").

Нужен быстрый workflow, который:
- действительно запускает обучение;
- даёт короткий feedback loop;
- даёт формальную pass/fail оценку по identity-сценариям;
- воспроизводим между прогонами.

## Goals / Non-Goals
- Goals:
  - добавить отдельный DAG для quick real-train identity hotfix;
  - добавить post-train identity eval и gate;
  - обеспечить воспроизводимые параметры запуска (seed + фиксированные inference settings).
- Non-Goals:
  - заменить основной production lifecycle DAG;
  - добавлять полный benchmark-suite качества модели;
  - вводить merge/full-finetune политику вне adapter-first подхода.

## Decisions
- Decision: реализовать отдельный DAG (а не ветвить основной lifecycle условными task-графами).
  - Почему: проще операционно, меньше риск регрессий в primary path.
- Decision: identity eval выполнять отдельным скриптом, который формирует машинно-читаемый summary.
  - Почему: упрощает gate-логику, повторное использование вне DAG и тестируемость.
- Decision: использовать quick профиль real-train (малые steps/epochs) как дефолт нового workflow.
  - Почему: быстрый feedback loop для ручных проверок pipeline.
- Decision: добавить seed-параметры в train/infer путь нового workflow.
  - Почему: практическая воспроизводимость при сравнении run-to-run.

## Risks / Trade-offs
- Риск: быстрый профиль может переобучаться на identity-примерах и ухудшать retention.
  - Mitigation: workflow позиционируется как hotfix/verification path, а не финальный релизный контур.
- Риск: even with fixed seeds возможны run-to-run расхождения на GPU.
  - Mitigation: фиксировать допуски и сравнивать метрики, а не требовать бит-в-бит совпадения.
- Риск: дополнительный DAG увеличивает операционный surface.
  - Mitigation: reuse существующих обёрток и единый runbook с диагностикой.

## Migration Plan
1. Добавить DAG и scripts/config для identity workflow без изменения primary DAG.
2. Добавить тесты на identity gate и контракт конфигурации.
3. Обновить документацию и примеры запуска.
4. Провести smoke запуск нового workflow на коротком датасете.

## Open Questions
- Нужен ли identity gate как обязательный release gate в основном lifecycle DAG или только в новом quick workflow?
- Какой стартовый порог pass-rate принять по умолчанию (`0.8` или `1.0`)?
