## ADDED Requirements

### Requirement: Reviewer-curated batch ingest для локального repo family
Система MUST поддерживать reviewer-curated ingest локального 1C repo family через `curation_batch_manifest`, а не только через bulk extraction.

#### Scenario: Batch manifest описывает набор файлов для review
- **WHEN** для прогона передан валидный `curation_batch_manifest` с `source_family_id` и списком файлов/модулей
- **THEN** система MUST запускать curating как batch-oriented workflow с coverage tracking по каждому файлу

#### Scenario: Batch manifest отсутствует или неполон
- **WHEN** отсутствует `curation_batch_manifest` или в нём нет достаточного file-level описания
- **THEN** система MUST завершать curating в статусе `FAIL` с явной диагностикой по intake contract

### Requirement: File-level provenance и coverage tracking
Система MUST сохранять file-level provenance и coverage status для reviewer-curated sample.

#### Scenario: Curated sample связан с просмотренным файлом
- **WHEN** reviewer формирует sample на основе просмотренного файла/модуля
- **THEN** sample MUST содержать ссылку на source file/module и MUST быть отражён в `coverage_report`

#### Scenario: Sample не имеет file-level provenance
- **WHEN** curated sample не содержит `source_file_ref` или coverage record
- **THEN** такой sample MUST быть отклонён до публикации релиза

### Requirement: Reviewer workflow не заменяется bulk extraction
Система MUST считать reviewer-curated ingest отдельным workflow и MUST NOT принимать raw bulk extraction как эквивалент review batch.

#### Scenario: Попытка опубликовать parser-derived sample без review batch
- **WHEN** sample получен из parser/bulk extraction без reviewer batch provenance
- **THEN** он MUST NOT считаться частью reviewer-curated корпуса
