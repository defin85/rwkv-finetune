## ADDED Requirements

### Requirement: Placement SWE-rebench-V2 в dataset contours
Система MUST относить derived sample из `SWE-rebench-V2` только к контуру `extended` и только к сегменту `coding_general`.

#### Scenario: Derived sample из SWE-rebench-V2 прошёл curating
- **WHEN** sample сформирован из допустимого instance `SWE-rebench-V2`
- **THEN** он MUST маркироваться как `extended` и `coding_general`
- **AND** он MUST NOT попадать в `core` contour

### Requirement: Русскоязычная нормализация prompt для SWE-rebench-V2
Система MUST формировать для derived sample `SWE-rebench-V2` русскоязычный `user_prompt` и MUST сохранять исходный англоязычный `problem_statement` с translation provenance в metadata.

#### Scenario: Подготовка derived sample к релизу
- **WHEN** допустимый instance `SWE-rebench-V2` преобразуется в канонический sample
- **THEN** итоговый `user_prompt` MUST быть на русском языке
- **AND** исходный `problem_statement` и translation provenance MUST сохраняться в metadata

#### Scenario: Derived sample не удовлетворяет языковой политике
- **WHEN** после normalisation `user_prompt` остаётся нерусскоязычным или translation provenance отсутствует
- **THEN** sample MUST быть исключён из train/eval релиза

### Requirement: Derived SFT target вместо raw task row
Система MUST публиковать `SWE-rebench-V2` в train только как derived SFT sample и MUST NOT использовать raw task row или raw execution logs как готовый train sample.

#### Scenario: Канонический sample сформирован из task instance
- **WHEN** система экспортирует derived sample из `SWE-rebench-V2`
- **THEN** train-артефакт MUST содержать `user_prompt`/`assistant_response`, а не прямую сериализацию исходной task row

#### Scenario: Попытка использовать raw task row как train sample
- **WHEN** сборка пытается опубликовать raw `problem_statement`/`patch`/execution metadata без derived normalisation
- **THEN** такой sample MUST быть отклонён до релизной сериализации

### Requirement: Patch-style guardrail для первого релиза
Система MUST NOT делать raw unified diff обязательным универсальным `assistant_response` форматом для `SWE-rebench-V2` в первом релизе.

#### Scenario: Основной поток derived sample для первого релиза
- **WHEN** система формирует основной релизный поток `SWE-rebench-V2` sample
- **THEN** `assistant_response` MUST быть нормализованным fix-oriented ответом
- **AND** raw `patch` MAY храниться в metadata, но MUST NOT быть единственным обязательным target-форматом для всего потока

### Requirement: Release cap для первого релиза с SWE-rebench-V2
Система MUST ограничивать долю `SWE-rebench-V2` не более чем `50%` сегмента `coding_general` в первом релизе, который использует этот источник.

#### Scenario: Доля SWE-rebench-V2 превышает cap
- **WHEN** pre-release проверка фиксирует долю `SWE-rebench-V2` выше `50%` сегмента `coding_general`
- **THEN** релиз MUST быть заблокирован до коррекции mix

#### Scenario: Доля SWE-rebench-V2 укладывается в cap
- **WHEN** доля `SWE-rebench-V2` не превышает `50%` сегмента `coding_general`
- **THEN** система MAY продолжать pipeline при прохождении остальных quality gates
