## ADDED Requirements

### Requirement: Локальный git repo family как trusted 1C источник
Система MUST поддерживать ingest одного или нескольких локальных git-репозиториев 1С как единого `source family` при наличии явного `repo_family_manifest`.

#### Scenario: Успешная инициализация ingest для source family
- **WHEN** для запуска переданы валидные `repo_roots[]`, `source_family_id`, `canonical_snapshot_root`, `training_permission` и usage policy
- **THEN** система MUST запускать ingest этого набора как одного logical source family, а не как независимых источников

#### Scenario: Отсутствует permission или family manifest
- **WHEN** отсутствует `repo_family_manifest` или в нём не задан `training_permission`
- **THEN** система MUST завершать сборку в статусе `FAIL` с явной диагностикой по отсутствующей метаинформации

### Requirement: Канонизация snapshot и overlap detection внутри source family
Система MUST выполнять exact overlap detection и канонизацию snapshot-содержимого между sibling-репозиториями одного source family до расчёта объёма корпуса.

#### Scenario: Идентичный путь и содержимое присутствуют в двух sibling snapshot
- **WHEN** одинаковый BSL-артефакт найден в нескольких репозиториях source family
- **THEN** система MUST учитывать его как один canonical sample и MUST фиксировать альтернативные origin references в отчёте

#### Scenario: Одинаковый путь имеет разное содержимое в sibling snapshot
- **WHEN** одинаковый относительный путь найден в нескольких репозиториях source family, но содержимое различается
- **THEN** система MUST использовать `canonical_snapshot_root` для выбора canonical snapshot и MUST фиксировать конфликт в release-report

### Requirement: Исторический ingest локализуемых BSL-изменений
Система MUST поддерживать ingest git history из локального source family для построения deterministic history-derived sample только из локализуемых изменений BSL-кода.

#### Scenario: Коммит содержит локализуемое изменение метода
- **WHEN** анализируемый коммит позволяет детерминированно выделить before/after изменение поддерживаемого BSL-метода
- **THEN** система MUST формировать history-derived sample с provenance до commit SHA, path и метода

#### Scenario: Коммит слишком широк или не даёт локализуемого BSL sample
- **WHEN** коммит изменяет слишком много файлов, зависит преимущественно от бинарных артефактов или не позволяет выделить поддерживаемый метод
- **THEN** система MUST пропускать такой коммит и MUST фиксировать причину skip в отчёте

### Requirement: Поддерживаемая trusted input surface для repo family v1
Система MUST включать в trusted ingest v1 только текстовые BSL snapshot/history артефакты source family и MUST исключать `.epf`-связанные BSL-модули из trusted контура.

#### Scenario: Snapshot содержит текстовый BSL-модуль из поддерживаемого дерева source family
- **WHEN** ingest обрабатывает текстовый BSL-модуль из поддерживаемого дерева source family
- **THEN** система MUST допускать такой артефакт в trusted ingest при соблюдении остальных правил provenance и canonicalization

#### Scenario: Snapshot или history содержит `.epf`-связанный BSL-модуль
- **WHEN** ingest обнаруживает BSL-артефакт, для которого trusted provenance опирается на `.epf`-связанный контекст
- **THEN** система MUST исключать такой артефакт из trusted v1 и MUST фиксировать причину исключения в отчёте
