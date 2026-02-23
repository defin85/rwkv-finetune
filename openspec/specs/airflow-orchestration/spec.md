# airflow-orchestration Specification

## Purpose
Определить обязательный Airflow-first orchestration-контур для жизненного цикла обучения адаптера (prepare/train/evaluate/release) с gate-блокировками, retry-policy и audit trail.
## Requirements
### Requirement: Airflow-first orchestration profile
Система MUST поддерживать Apache Airflow как primary orchestration profile для train lifecycle.

#### Scenario: Выбор Airflow как primary runtime
- **WHEN** команда активирует профиль `airflow`
- **THEN** запуск обучающего pipeline MUST выполняться через Airflow DAG, а не через ad-hoc последовательность ручных shell-команд

### Requirement: Primary Airflow enforcement policy
Система MUST использовать `airflow` как единственный primary orchestration profile. Конфигурации с primary=`mlops-lite` или с одновременной активацией `mlops-lite` и `airflow` MUST отклоняться.

#### Scenario: Попытка активировать `mlops-lite` как primary
- **WHEN** в deployment-конфигурации primary profile установлен в `mlops-lite`
- **THEN** система MUST отклонять такую конфигурацию и требовать `airflow` как primary path

#### Scenario: Попытка одновременного включения двух primary профилей
- **WHEN** в deployment-конфигурации одновременно активированы `mlops-lite` и `airflow` как primary path
- **THEN** система MUST отклонять такую конфигурацию как невалидную до явного выбора одного профиля

### Requirement: DAG-контракт стадий обучения
Система MUST реализовывать DAG со стадиями `prepare_dataset`, `train_adapter`, `evaluate_adapter`, `release_adapter` и с явными зависимостями между стадиями.

#### Scenario: Успешное выполнение DAG
- **WHEN** входные артефакты валидны и все стадии завершаются успешно
- **THEN** DAG MUST завершаться в terminal-success статусе с полным набором выходных артефактов по стадиям

#### Scenario: Ошибка стадии train
- **WHEN** `train_adapter` завершается с ошибкой
- **THEN** downstream стадии `evaluate_adapter` и `release_adapter` MUST не выполняться, а DAG MUST фиксировать failure status

### Requirement: Shell-wrapper reuse contract
Система MUST использовать существующие shell wrappers (`prepare_binidx.sh`, `train.sh`, `train_*.sh`) как исполняемые unit-операции внутри Airflow tasks.

#### Scenario: Запуск задачи подготовки данных из DAG
- **WHEN** выполняется задача `prepare_dataset`
- **THEN** Airflow task MUST вызывать штатный скрипт подготовки данных и валидировать наличие ожидаемого binidx output

### Requirement: GPU serialization policy
Система MUST сериализовать GPU-bound задачи обучения и оценки через Airflow pool с ограничением concurrency.

#### Scenario: Два одновременных trigger одного DAG
- **WHEN** две DAG-run с GPU-bound задачами стартуют близко по времени
- **THEN** в каждый момент времени MUST выполняться не более одной GPU-bound задачи, а остальные MUST ожидать в очереди pool

### Requirement: Retry and audit trail policy
Система MUST поддерживать управляемые retries/backoff для recoverable ошибок и MUST сохранять audit trail статусов и причин неуспеха по задачам DAG.

#### Scenario: Recoverable failure на стадии prepare
- **WHEN** стадия `prepare_dataset` падает из-за временной recoverable ошибки
- **THEN** Airflow MUST выполнять повторные попытки по заданной retry-policy и фиксировать историю попыток

### Requirement: Release-gate enforcement in Airflow DAG
Система MUST блокировать `release_adapter`, если не выполнены quality/eval требования: PASS quality gates датасета, PASS `domain eval`, PASS `retention eval`.

#### Scenario: Провал retention eval перед релизом
- **WHEN** `evaluate_adapter` возвращает retention verdict `FAIL`
- **THEN** `release_adapter` MUST не запускаться, а причина блокировки MUST фиксироваться в артефактах run

#### Scenario: Dataset quality status невалиден
- **WHEN** входной dataset release имеет критический quality status
- **THEN** DAG MUST блокировать переход к `train_adapter` до устранения нарушений
