## ADDED Requirements

### Requirement: Versioned 1C pattern букварь как curator artifact
Система MUST поддерживать versioned `1C pattern букварь` как отдельный curator/rubric artifact для reviewer-curated workflow и MUST NOT трактовать его как train-corpus.

#### Scenario: Публикуется новый релиз букваря
- **WHEN** команда выпускает новую версию `1C pattern букваря`
- **THEN** релиз MUST иметь явный versioned manifest
- **AND** релиз MUST содержать pattern catalog и source manifest
- **AND** релиз MUST NOT позиционироваться как готовый train-set

### Requirement: Source hierarchy и evidence policy для pattern extraction
Система MUST использовать иерархию источников и evidence tiers при подготовке pattern cards: `kb.1ci.com` как primary normative source, `its.1c.ru` export как supporting practical source, книги/пособия как supporting conceptual source и локальный repo family как code exemplars.

#### Scenario: Источники согласованы между собой
- **WHEN** pattern card опирается на несколько источников
- **THEN** она MUST сохранять source refs и evidence tier для каждого источника

#### Scenario: Supporting source конфликтует с normative source
- **WHEN** практический или концептуальный источник противоречит `kb.1ci.com`
- **THEN** pattern card MUST следовать `kb.1ci.com`
- **AND** конфликт MUST быть отражён в curator notes или source refs

### Requirement: Contract pattern card для 1C букваря
Система MUST представлять каждый элемент букваря как `pattern_card` с обязательными полями: `pattern_id`, `title`, `general_principle`, `1c_adaptation_note`, `when_to_apply`, `when_not_to_apply`, `positive_signals`, `anti_patterns`, `search_cues`, `sample_class_mapping`, `source_refs`, `evidence_tier`.

#### Scenario: В каталог добавляется новый паттерн
- **WHEN** новый паттерн включается в versioned букварь
- **THEN** он MUST иметь полный набор обязательных полей
- **AND** отсутствие `1c_adaptation_note` или `when_not_to_apply` MUST блокировать публикацию этого паттерна

### Requirement: General principle -> 1C projection policy
Система MUST формулировать паттерны букваря как проекцию общего инженерного принципа на ограничения и идиомы 1C, а не как догматический перенос практик из других языков.

#### Scenario: Паттерн основан на общем инженерном принципе
- **WHEN** curator использует общий принцип проектирования или рефакторинга
- **THEN** pattern card MUST явно описывать, как этот принцип адаптируется к 1C
- **AND** pattern card MUST указывать, где такая адаптация НЕ должна применяться

### Requirement: Reference-text используется как rubric/evidence layer
Система MUST использовать `kb.1ci.com`, ИТС и книги как источники rubric, evidence и rationale, но MUST NOT использовать long-form reference-text как bulk train-content внутри букваря.

#### Scenario: Pattern card использует внешний reference source
- **WHEN** curator добавляет в pattern card материал из документации, ИТС или книги
- **THEN** card MAY содержать citation note, summary или короткий reference excerpt
- **AND** card MUST NOT содержать длинный verbatim fragment, достаточный для роли train-target

### Requirement: Handoff к reviewer-curated workflow через stable pattern identifiers
Система MUST публиковать `pattern_id`, `search_cues` и `sample_class_mapping` так, чтобы reviewer-curated batches могли ссылаться на pattern cards как на стабильный input contract.

#### Scenario: Reviewer-curated batch готовится по букварю
- **WHEN** curator формирует batch reviewer-curated sample на основе букваря
- **THEN** batch MUST ссылаться на один или несколько `pattern_id`
- **AND** поиск code exemplars MUST опираться на `search_cues`
- **AND** наличие `search_cues` MUST NOT заменять обязательный file-level review
