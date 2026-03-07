## ADDED Requirements

### Requirement: Trusted policy для локального repo-family корпуса
Система MUST относить к trusted/core контуру только deterministic sample, извлечённые из локального 1C source family без LLM-generated semantic enrichment.

#### Scenario: Детерминированный snapshot/history sample
- **WHEN** sample построен из snapshot BSL, локализуемого history diff или metadata-linked context без модельного перефразирования
- **THEN** sample MUST быть допустим для trusted/core контура при наличии полного provenance

#### Scenario: Sample требует LLM-generated paraphrase или explanation
- **WHEN** для формирования sample требуется модельно-сгенерированное объяснение, summary или иное semantic enrichment
- **THEN** такой sample MUST NOT попадать в trusted/core release и MUST быть либо отклонён, либо переведён в `extended` контур по отдельной policy

### Requirement: Split policy для одного source family
Система MUST строить train/dev/eval split для локального repo family по времени и lineage изменений и MUST NOT использовать sibling-репозитории одной конфигурации как независимые границы split.

#### Scenario: Два sibling-репозитория одной конфигурации
- **WHEN** два локальных git-репозитория описаны одним `source_family_id`
- **THEN** система MUST рассматривать их как один источник при split и MUST NOT считать разбиение "по repo name" достаточной защитой от leakage

#### Scenario: Формирование holdout из поздних изменений
- **WHEN** система выделяет dev/eval holdout из более поздних commit lineage внутри source family
- **THEN** она MUST исключать из train exact и near duplicates, связанные с тем же lineage, до публикации релиза

#### Scenario: Первый trusted release без отдельного task-family holdout
- **WHEN** публикуется первый trusted release для source family и temporal/lineage split с near-dedup уже настроен
- **THEN** система MUST считать такой split достаточным для v1 и MUST NOT блокировать релиз только из-за отсутствия отдельного holdout по семействам задач/директорий

### Requirement: Честный расчёт объёма trusted корпуса
Система MUST считать объём trusted корпуса по уникальным sample после exact/near dedup и overlap canonicalization и MUST NOT добивать целевой объём synthetic filler-данными.

#### Scenario: Уникальный trusted объём ниже целевого target
- **WHEN** `attained_unique_volume_mb` после dedup ниже желаемого target, но выше обязательного hard minimum
- **THEN** система MUST публиковать release-report с явным дефицитом объёма и MAY продолжать pipeline без synthetic padding

#### Scenario: Попытка добить trusted release synthetic filler-данными
- **WHEN** сборка пытается компенсировать дефицит trusted объёма дубликатами, synthetic sample или LLM-enriched sample
- **THEN** такие sample MUST NOT учитываться в trusted объёме релиза

### Requirement: Hard minimum gate для trusted repo-family release
Система MUST применять обязательный hard minimum к `attained_unique_volume_mb` локального trusted repo-family корпуса и MUST блокировать релиз ниже этого порога.

#### Scenario: Уникальный trusted объём достигает hard minimum
- **WHEN** `attained_unique_volume_mb` после dedup и canonicalization не ниже обязательного hard minimum
- **THEN** система MUST разрешать публикацию trusted repo-family release при прохождении остальных quality gates

#### Scenario: Уникальный trusted объём ниже hard minimum
- **WHEN** `attained_unique_volume_mb` после dedup и canonicalization ниже обязательного hard minimum
- **THEN** система MUST завершать release в статусе `FAIL` и MUST публиковать диагностический отчёт с величиной дефицита
