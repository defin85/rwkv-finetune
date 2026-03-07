## ADDED Requirements

### Requirement: Local staged ingest источника SWE-rebench-V2
Система MUST поддерживать ingest локального snapshot `nebius/SWE-rebench-V2` как внешнего future-source для derived SFT sample при наличии явного source manifest.

#### Scenario: Успешная инициализация ingest staged snapshot
- **WHEN** для сборки переданы локальный snapshot `SWE-rebench-V2`, `dataset_id`, `snapshot_ref`, `origin_ref` и `source_kind=issue_based`
- **THEN** система MUST запускать ingest этого snapshot как воспроизводимого external source без сетевой зависимости на этапе build

#### Scenario: Отсутствует snapshot или source manifest
- **WHEN** локальный snapshot `SWE-rebench-V2` отсутствует либо не задан обязательный source manifest
- **THEN** система MUST завершать сборку в статусе `FAIL` с явной диагностикой по отсутствующему входу

### Requirement: Граница v1 для SWE-rebench-V2 source
Система MUST ограничивать `v1` support только issue-based corpus `nebius/SWE-rebench-V2` и MUST NOT включать `SWE-rebench-V2-PRs` в этот ingest-контур.

#### Scenario: Попытка подключить PR corpus в v1
- **WHEN** ingest получает `dataset_id` или staging path, относящийся к `SWE-rebench-V2-PRs`
- **THEN** система MUST отклонять такой источник для этого change и MUST фиксировать причину в отчёте

### Requirement: Eligibility gate для instance-level ingest
Система MUST принимать в curating только те instance `SWE-rebench-V2`, где заполнены обязательные provenance и task поля.

#### Scenario: Instance содержит обязательные поля
- **WHEN** instance содержит `instance_id`, `repo`, `base_commit`, `problem_statement`, `patch`, `license` и непустой `FAIL_TO_PASS`
- **THEN** instance MUST считаться допустимым кандидатом для derived normalisation при прохождении остальных quality gates

#### Scenario: Instance теряет provenance или task completeness
- **WHEN** хотя бы одно из обязательных полей отсутствует или пусто
- **THEN** instance MUST быть исключён из derived source и MUST получить явный `exclusion_reason`

### Requirement: Сохранение rich metadata для аудита
Система MUST сохранять sample-level metadata из `SWE-rebench-V2`, достаточную для аудита и будущих execution-oriented итераций, даже если execution runtime не используется в `v1`.

#### Scenario: Нормализация допустимого instance
- **WHEN** instance проходит eligibility stage
- **THEN** его metadata MUST сохранять как минимум `test_patch`, `PASS_TO_PASS`, `interface`, `meta`, `origin_ref`, `snapshot_ref` и instance-level `license`
