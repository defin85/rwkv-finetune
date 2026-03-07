## ADDED Requirements

### Requirement: Placement reviewer-curated 1C corpus в contours
Система MUST относить reviewer-curated 1C pattern corpus к контуру `extended` и сегменту `onec_bsl`.

#### Scenario: Curated sample прошёл review workflow
- **WHEN** sample сформирован в рамках reviewer-curated workflow и прошёл quality gates
- **THEN** он MUST маркироваться как `extended` и `onec_bsl`
- **AND** он MUST NOT публиковаться как `core trusted` sample

### Requirement: Pattern-oriented taxonomy для reviewer-curated sample
Система MUST поддерживать reviewer-curated sample-классы `pattern_generation`, `pattern_refactor`, `pattern_review`, `pattern_explanation`.

#### Scenario: Curated sample включён в релиз
- **WHEN** sample принят в reviewer-curated release
- **THEN** он MUST иметь один из поддерживаемых pattern classes и соответствующую task category

### Requirement: Generalization и decontextualization policy
Система MUST принимать в reviewer-curated corpus только такие sample, которые обучают переносимому 1C-паттерну и не зависят критически от уникальной бизнес-специфики исходной конфигурации.

#### Scenario: Sample выражает переносимый 1C-паттерн
- **WHEN** reviewer может сформулировать generalization note, объясняющую переносимый паттерн, smell или refactoring path
- **THEN** sample MAY быть включён в reviewer-curated release при наличии полного provenance

#### Scenario: Sample остаётся конфигурационно-специфичным
- **WHEN** ценность sample определяется в основном уникальными названиями объектов, регистров или бизнес-процессов исходной конфигурации
- **THEN** такой sample MUST быть отклонён или переработан до переносимого вида до релиза

### Requirement: Reviewer rationale как обязательное metadata поле
Система MUST сохранять reviewer rationale и generalization note для каждого reviewer-curated sample.

#### Scenario: Sample проходит release validation
- **WHEN** reviewer-curated sample проверяется перед публикацией
- **THEN** отсутствие `reviewer_rationale` или `generalization_note` MUST блокировать включение sample в релиз

### Requirement: Incremental batch workflow для token-constrained curation
Система MUST поддерживать incremental batching reviewer-curated workflow, чтобы corpus можно было строить по частям без потери coverage и traceability.

#### Scenario: Corpus собирается несколькими review batches
- **WHEN** reviewer-curated corpus формируется в несколько отдельных batch-прогонов
- **THEN** система MUST агрегировать coverage и release provenance без потери связи sample с исходным batch
