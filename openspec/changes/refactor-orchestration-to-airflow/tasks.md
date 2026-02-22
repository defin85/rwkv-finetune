## 1. Airflow foundation
- [ ] 1.1 Добавить базовый runtime-профиль Apache Airflow (конфиг, metadata DB, запуск scheduler/webserver) для WSL-среды.
- [ ] 1.2 Зафиксировать orchestration profile selection (`mlops-lite` XOR `airflow`) и критерии выбора primary runtime.
- [ ] 1.3 Определить структуру каталогов Airflow-артефактов и логику хранения state/logs.

## 2. DAG и task-контракты
- [ ] 2.1 Реализовать DAG с этапами `prepare_dataset -> train_adapter -> evaluate_adapter -> release_adapter`.
- [ ] 2.2 Интегрировать существующие shell wrappers как task payload (без переписывания RWKV-PEFT train logic).
- [ ] 2.3 Добавить контракты входов/выходов для каждой task и fail-fast валидацию обязательных артефактов.

## 3. Надёжность и ресурсы
- [ ] 3.1 Настроить retries/backoff и policy остановки DAG при критических сбоях.
- [ ] 3.2 Настроить Airflow pool для сериализации GPU-bound задач (concurrency=1).
- [ ] 3.3 Добавить устойчивый audit trail статусов задач и причин блокировки release.

## 4. Quality/Eval gates в Airflow flow
- [ ] 4.1 Интегрировать проверку статуса quality gates датасета перед `train_adapter`.
- [ ] 4.2 Интегрировать обязательные `domain eval` и `retention eval` перед `release_adapter`.
- [ ] 4.3 Блокировать выпуск адаптера в DAG при провале хотя бы одного gate.

## 5. Валидация и документация
- [ ] 5.1 Провести smoke-run DAG на коротком профиле и зафиксировать expected outputs по каждой стадии.
- [ ] 5.2 Обновить `README.md` и `AGENTS.md` под Airflow operational path.
- [ ] 5.3 Подготовить runbook: запуск, восстановление после fail, rollback к предыдущему стабильному адаптеру.

## 6. Зависимости и параллелизация
- [ ] 6.1 Зависимость: блок 1 MUST быть завершён до блоков 2-4.
- [ ] 6.2 Зависимость: блок 4 MUST быть завершён до 5.1.
- [ ] 6.3 Параллелизация: 5.2 и 5.3 можно выполнять параллельно после 5.1.
