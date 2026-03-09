## ADDED Requirements

### Requirement: Мульти-источниковый ingest-контур 1C core корпуса
Система MUST поддерживать сборку 1C core корпуса одновременно из трёх обязательных источников:
- экспорт конфигурации 1C;
- выгрузка синтаксис-помощника;
- snapshot документации `kb.1ci.com`.

#### Scenario: Успешная инициализация ingest по трём источникам
- **WHEN** для запуска сборки переданы валидные входы всех трёх источников
- **THEN** система MUST запускать ingest по каждому источнику в рамках одного релизного прогона

#### Scenario: Отсутствует обязательный источник
- **WHEN** хотя бы один из трёх обязательных источников отсутствует или недоступен
- **THEN** система MUST завершать сборку в статусе `FAIL` с явной причиной в отчёте

### Requirement: Канонический sample-контракт merged 1C core корпуса
Система MUST нормализовать записи из всех трёх источников в канонический sample-контракт `user_prompt` / `assistant_response` + metadata до этапа profile-specific serialization.

#### Scenario: Валидная запись источника проходит normalisation
- **WHEN** ingest обрабатывает валидную запись из `config export`, `syntax helper export` или `kb.1ci.com` snapshot
- **THEN** итоговый sample MUST содержать `user_prompt`, `assistant_response`, `source_type`, `origin_ref`, `license`
- **AND** sample MUST оставаться совместимым с общими provenance/lang/quality требованиями dataset strategy

#### Scenario: Ingest пытается зафиксировать profile wire format как внутренний контракт
- **WHEN** merged core ingest пытается сделать `Instruction/Response + <|endoftext|>` обязательным внутренним форматом sample
- **THEN** такая реализация MUST считаться несоответствующей ingest contract
- **AND** profile-specific serialization MUST выполняться на уровне release profile

### Requirement: Адаптер экспорта конфигурации 1C
Система MUST извлекать из экспорта конфигурации 1C процедуры и функции как отдельные sample для 1C core корпуса.

#### Scenario: Извлечение методов из конфигурации
- **WHEN** ingest обрабатывает экспорт модулей конфигурации
- **THEN** каждая найденная процедура/функция MUST экспортироваться как отдельный sample с `origin_ref` на модуль

### Requirement: Адаптер выгрузки синтаксис-помощника
Система MUST поддерживать ingest выгрузки синтаксис-помощника в нормализованный sample-формат для обучения.

#### Scenario: Нормализация записи синтаксис-помощника
- **WHEN** ingest получает валидную запись из выгрузки синтаксис-помощника
- **THEN** запись MUST преобразовываться в канонический sample с заполненными `user_prompt`, `assistant_response`, `source_type`, `origin_ref`, `license`

#### Scenario: Неподдерживаемый формат выгрузки синтаксис-помощника
- **WHEN** входной формат выгрузки синтаксис-помощника не поддерживается контрактом
- **THEN** система MUST завершать сборку в статусе `FAIL` с диагностикой по формату

### Requirement: Политика ingest документации `kb.1ci.com`
Система MUST принимать в documentation-контур только страницы, происходящие из домена `kb.1ci.com`, с обязательной фиксацией `origin_ref`.

#### Scenario: Попытка добавить страницу из нерелевантного домена
- **WHEN** ingest получает источник документации вне домена `kb.1ci.com`
- **THEN** источник MUST быть отклонён и релиз MUST блокироваться до устранения нарушения

#### Scenario: Успешная обработка страницы документации
- **WHEN** ingest обрабатывает страницу из `kb.1ci.com`
- **THEN** сформированный sample MUST содержать ссылку на исходную страницу в `origin_ref`

### Requirement: Provenance и лицензионная трассировка
Система MUST сохранять provenance и license метаинформацию для каждого sample, полученного из всех трёх источников.

#### Scenario: Проверка метаинформации sample
- **WHEN** sample проходит quality stage перед merge
- **THEN** sample без обязательных provenance/license полей MUST отклоняться

### Requirement: Объёмный gate 1C core корпуса
Система MUST обеспечивать объём merged 1C core корпуса в диапазоне `300 MB .. 1 GB` до этапа итогового mix профиля.

#### Scenario: Объём ниже минимального порога core корпуса
- **WHEN** размер merged 1C core корпуса меньше `300 MB`
- **THEN** релиз MUST блокироваться с причиной дефицита объёма

#### Scenario: Объём в целевом диапазоне core корпуса
- **WHEN** размер merged 1C core корпуса находится в диапазоне `300 MB .. 1 GB`
- **THEN** система MAY продолжать pipeline на этап profile mix

### Requirement: Интеграция с профилем 1C-Expert-v4
Система MUST использовать merged 1C core корпус как вход сегмента `onec_bsl` в профиле `1C-Expert-v4`, сохраняя совместимость с его mix и quality gates.

#### Scenario: Передача core корпуса в этап profile mix
- **WHEN** merged 1C core корпус прошёл source-ingestion quality gates
- **THEN** этап `1C-Expert-v4` profile mix MUST использовать этот корпус как источник сегмента `onec_bsl`
- **AND** profile formatter MUST применять `Instruction/Response + <|endoftext|>` только после этого handoff
