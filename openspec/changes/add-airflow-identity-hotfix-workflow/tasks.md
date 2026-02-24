## 1. Airflow DAG и контракт конфигурации
- [ ] 1.1 Добавить новый DAG быстрого real-train workflow (identity hotfix) с явными стадиями prepare -> train -> identity-eval -> identity-gate.
- [ ] 1.2 Задать и валидировать контракт `dag_run.conf` для нового DAG (пути к данным/модели, run_name, порог gate, inference-параметры, seed-параметры).
- [ ] 1.3 Обеспечить audit trail для всех стадий и запись причин fail в gate-артефакты.

## 2. Реальная оценка identity после обучения
- [ ] 2.1 Реализовать скрипт identity evaluation, который запускает inference на фиксированном наборе промптов и пишет `identity_eval_summary.json`.
- [ ] 2.2 Реализовать identity gate с порогом pass-rate и явным fail-reason при провале.
- [ ] 2.3 Гарантировать, что workflow использует реальный train wrapper, а не smoke stub.

## 3. Быстрый и воспроизводимый train-профиль
- [ ] 3.1 Добавить quick-train wrapper/profile для короткого запуска (малый `epoch_steps`, `epoch_count=1`, low-VRAM friendly quant profile).
- [ ] 3.2 Добавить поддержку/прокидывание `random_seed` в train-путь workflow.
- [ ] 3.3 Зафиксировать дефолтные inference seed/параметры для повторяемых identity-проверок.

## 4. Тесты и валидация
- [ ] 4.1 Добавить unit/logic тесты для identity gate (PASS/FAIL сценарии, отсутствие артефактов, пороговые значения).
- [ ] 4.2 Добавить проверку конфигурационного контракта нового DAG.
- [ ] 4.3 Прогнать релевантные тесты и зафиксировать результаты.

## 5. Документация
- [ ] 5.1 Обновить `README.md` инструкцией запуска нового workflow.
- [ ] 5.2 Обновить `docs/airflow-runbook.md` (операционный цикл, диагностика fail identity gate, rollback path).
- [ ] 5.3 Добавить примеры `conf.json` для быстрого запуска identity hotfix.
