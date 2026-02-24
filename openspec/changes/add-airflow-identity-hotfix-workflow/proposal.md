# Change: Добавить Airflow workflow быстрого реального обучения для identity hotfix (RWKV-7)

## Why
Нужен отдельный короткий сценарий **реального** обучения (без smoke-stub), чтобы быстро и воспроизводимо проверять обучающий pipeline на практическом дефекте: модель отвечает, что она `Qwen`, хотя ожидается `RWKV-7`.

Текущий основной lifecycle-DAG покрывает общий train/eval/release контур, но не даёт целевого identity-gate и стандартизированной быстрой процедуры проверки этого класса регрессий.

## What Changes
- Добавить отдельный Airflow DAG для быстрого real-train workflow под identity hotfix.
- Добавить post-train identity evaluation stage с вычислением pass-rate по фиксированному набору промптов.
- Добавить identity gate (порог pass-rate), который блокирует успешное завершение workflow при провале.
- Добавить конфигурационные параметры воспроизводимости для workflow:
  - train seed;
  - inference seed;
  - фиксированные inference-параметры (`tokens`, `temperature`, `noise`).
- Добавить дефолтные quick-train профиль/обёртку для короткого запуска и получения результата в пределах короткой сессии.

## Impact
- Affected specs: `airflow-orchestration`.
- Affected code:
  - `orchestration/airflow/dags/` (новый DAG + контракты конфигурации);
  - `scripts/` (identity eval script + quick-train wrapper/profile wiring);
  - `configs/` (набор identity-промптов и/или профиль);
  - `README.md`, `docs/airflow-runbook.md` (процедура запуска/диагностики нового workflow).
