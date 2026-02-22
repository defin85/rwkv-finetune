# Decision Memo: `refactor-mlops-lite-workflow` vs `refactor-orchestration-to-airflow`

Дата: 2026-02-22

## Контекст
Сравниваются два взаимоисключающих варианта оркестрации training pipeline RWKV v7:
- `refactor-mlops-lite-workflow`
- `refactor-orchestration-to-airflow`

Оба варианта опираются на существующий shell pipeline (`prepare_binidx -> train -> evaluate/release`) и policy качества данных из `add-1c-dataset-strategy`.

## Сравнительная таблица

| Критерий | MLOps-lite (`refactor-mlops-lite-workflow`) | Airflow (`refactor-orchestration-to-airflow`) |
|---|---|---|
| Архитектурный подход | File-based orchestration, минимальная обвязка | DAG-based orchestration через Apache Airflow |
| Сложность внедрения | Низкая/средняя | Средняя/высокая |
| Инфраструктурные требования | Минимальные (локальная среда и скрипты) | Выше (Airflow runtime, metadata DB, scheduler/webserver) |
| Time-to-value | Быстрый старт | Медленнее из-за setup orchestration слоя |
| Операционная нагрузка | Низкая | Выше (обслуживание Airflow) |
| Контроль зависимостей стадий | Есть, но легче «сорвать» вручную | Строгий через DAG dependency graph |
| Retry/Backoff | Нужно реализовывать вручную в обвязке | Нативно в Airflow task policy |
| Наблюдаемость и audit trail | Через локальные manifest-артефакты | Через Airflow UI + task logs + артефакты |
| GPU-конкуренция | Контроль вручную (или простые lock/pool механизмы) | Нативно через Airflow pools/concurrency policy |
| Масштабирование на несколько пайплайнов | Ограниченное, требует кастомной эволюции | Лучше подходит для роста количества DAG/run |
| Риск overengineering для текущего масштаба | Низкий | Повышенный |
| Риск «операционной хрупкости» при росте команды | Средний | Ниже за счёт стандартизации orchestration |
| Соответствие текущему контексту (WSL, no Docker, single GPU) | Очень высокое | Умеренное/высокое (возможно, но тяжелее) |
| Цена ошибки внедрения | Ниже | Выше |

## Практический выбор

### Выбирать `refactor-mlops-lite-workflow`, если
- команда маленькая (1-2 инженера);
- один основной training pipeline и редкие параллельные запуски;
- приоритет — быстрый результат и минимальная операционная сложность;
- нет явной потребности в централизованном scheduler/UI прямо сейчас.

### Выбирать `refactor-orchestration-to-airflow`, если
- ожидается несколько регулярных pipeline-ов и частые retrain циклы;
- нужна строгая DAG-оркестрация, retries, очереди и централизованный мониторинг;
- команда готова поддерживать отдельный orchestration runtime;
- операционная дисциплина важнее скорости первого релиза.

## Decision Rule (кратко)

- Если целевой горизонт 1-3 месяца и single-node workload: выбрать `refactor-mlops-lite-workflow`.
- Если горизонт 6+ месяцев с ростом числа запусков и участников: выбрать `refactor-orchestration-to-airflow`.

## Рекомендуемая последовательность (если нужен компромисс)

1. Сначала принять `refactor-mlops-lite-workflow` как быстрый baseline.
2. Через 1-2 релизных цикла проверить фактическую нагрузку (число run/неделя, доля ручных ретраев, инциденты из-за оркестрации).
3. При превышении порогов операционной боли — мигрировать на `refactor-orchestration-to-airflow`.

## Пороговые сигналы для перехода на Airflow

- >10 production-like run в неделю;
- >2 активных инженера, запускающих pipeline;
- регулярные инциденты из-за ручной координации стадий;
- необходимость стабильного расписания/backfill и централизованного SLA по запускам.
