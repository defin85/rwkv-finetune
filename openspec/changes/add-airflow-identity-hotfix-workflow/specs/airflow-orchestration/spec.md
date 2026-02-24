## ADDED Requirements
### Requirement: Dedicated identity-hotfix Airflow workflow
Система MUST предоставлять отдельный Airflow workflow для быстрого **реального** обучения под identity hotfix, независимый от smoke-stub режима.

#### Scenario: Успешный быстрый real-train прогон
- **WHEN** команда запускает identity-hotfix workflow с валидным `input_jsonl`, `load_model` и quick-train profile
- **THEN** workflow MUST выполнить стадии подготовки данных, обучения и post-train identity evaluation
- **AND** в `runs/<run_name>/` MUST быть сохранены train-артефакты и summary identity evaluation

#### Scenario: Некорректная train-конфигурация
- **WHEN** в конфигурации workflow отсутствует обязательный train input (`load_model` или `data_prefix`/входные артефакты)
- **THEN** workflow MUST завершаться с fail на стадии train с явной причиной в audit trail

### Requirement: Identity evaluation gate
Система MUST выполнять post-train identity gate и блокировать успешное завершение workflow при провале порога по identity-проверке.

#### Scenario: Identity check пройден
- **WHEN** pass-rate по identity prompt set >= заданного порога
- **THEN** identity gate MUST выставлять `PASS` и workflow MAY переходить в terminal-success

#### Scenario: Модель продолжает отвечать "Qwen"
- **WHEN** identity evaluation фиксирует ответ, нарушающий ожидаемую identity policy (в т.ч. ответы вида "я Qwen"), и итоговый pass-rate ниже порога
- **THEN** identity gate MUST выставлять `FAIL`
- **AND** причина MUST быть записана в gate artifact и audit trail

### Requirement: Reproducibility controls for quick identity workflow
Система MUST поддерживать конфигурационные параметры воспроизводимости для quick identity workflow.

#### Scenario: Повторный запуск с одинаковой конфигурацией
- **WHEN** workflow запускается повторно с одинаковыми dataset/model/profile и фиксированными `train_seed` + `inference_seed`
- **THEN** workflow MUST формировать сравнимые identity-eval результаты (в пределах заранее заданного operational tolerance)
- **AND** используемые seed/параметры inference MUST фиксироваться в summary артефактах
