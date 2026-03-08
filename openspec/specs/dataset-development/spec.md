# dataset-development Specification

## Purpose
TBD - created by archiving change add-1c-dataset-strategy. Update Purpose after archive.
## Requirements
### Requirement: Lifecycle версий датасета
Система MUST поддерживать формальный lifecycle версий датасета для дообучения RWKV v7 с этапами ingest, normalise, validate, split и release.

#### Scenario: Выпуск версии датасета
- **WHEN** команда готовит новый релиз датасета
- **THEN** формируется versioned-набор данных и фиксируется результат каждого этапа lifecycle

#### Scenario: Воспроизводимость релиза
- **WHEN** команда повторно запускает пайплайн на том же входном наборе и конфигурации
- **THEN** система MUST выдавать воспроизводимый состав релиза и эквивалентный `manifest`

### Requirement: Двухконтурная модель источников и provenance
Система MUST разделять источники на контуры `core` и `extended` и вести provenance для каждого образца в `manifest`.

#### Scenario: Добавление образца из mixed-use источника
- **WHEN** в датасет добавляется образец из mixed-use источника
- **THEN** образец MUST маркироваться как `extended` и содержать поля происхождения и лицензии

#### Scenario: Аудит происхождения
- **WHEN** требуется аудит конкретного образца
- **THEN** система MUST предоставлять трассировку до исходного источника и версии происхождения

### Requirement: Языковая политика промптов
Система MUST принимать в обучающий датасет только те образцы, где поле `user_prompt` сформулировано на русском языке.

#### Scenario: Проверка языка перед релизом
- **WHEN** образец проходит стадию валидации
- **THEN** образец с нерусским пользовательским промптом MUST быть исключён из train/eval наборов

### Requirement: Канонический sample-контракт и профильная сериализация
Система MUST хранить канонические образцы в структуре `user_prompt`/`assistant_response` + metadata и MUST выполнять релизную сериализацию через профильный formatter/export adapter.

#### Scenario: Подготовка релизного train-артефакта для профиля
- **WHEN** команда формирует релиз для конкретного профиля датасета
- **THEN** система MUST применять formatter, соответствующий этому профилю
- **AND** форматные проверки профиля MUST быть выполнены до токенизации

#### Scenario: Профиль `1C-Expert-v4` как конкретизация сериализации
- **WHEN** выбран профиль `1C-Expert-v4`
- **THEN** train-артефакт MUST сериализоваться в plain text формате `Instruction:`/`Response:` с маркером `<|endoftext|>` на sample
- **AND** стратегические требования по provenance/quality/language MUST сохраняться без ослабления

### Requirement: Покрытие типов задач
Система MUST поддерживать таксономию задач минимум из категорий: генерация кода, рефакторинг, запросы 1C, объяснение/ревью.

#### Scenario: Формирование релиза с балансом задач
- **WHEN** формируется релиз датасета
- **THEN** каждая обязательная категория MUST присутствовать в составе релиза и быть отражена в `manifest`

### Requirement: Базовый баланс категорий для первых релизов
Система MUST обеспечивать базовый баланс категорий задач для первых релизов датасета: генерация 35%, рефакторинг 35%, запросы 1C 15%, объяснение/ревью 15%, с допустимым отклонением не более 5 процентных пунктов по каждой категории.

#### Scenario: Проверка баланса категорий перед релизом
- **WHEN** система выполняет pre-release валидацию датасета
- **THEN** релиз MUST блокироваться, если любая категория выходит за пределы допустимого отклонения

#### Scenario: Паритет генерации и рефакторинга
- **WHEN** рассчитывается фактическое распределение категорий
- **THEN** доли генерации и рефакторинга MUST оставаться паритетными в пределах допустимого отклонения

### Requirement: Quality gates перед выпуском
Система MUST применять quality gates до выпуска версии: exact/near dedup, синтаксическая проверка BSL, фильтрация секретов/PII и контроль leakage.

#### Scenario: Обнаружен критический дефект качества
- **WHEN** любой из quality gates возвращает критическое нарушение
- **THEN** выпуск версии MUST быть заблокирован до устранения нарушения

#### Scenario: Проверка leakage между train и eval
- **WHEN** система выполняет контроль пересечений train/eval
- **THEN** образцы, нарушающие правила split и near-dedup, MUST исключаться или перераспределяться до публикации релиза

### Requirement: Стратегия оценки и итеративного улучшения
Система MUST поддерживать отдельные eval-наборы для генерации и рефакторинга и использовать результаты оценки для следующей итерации curating.

#### Scenario: Завершение обучающего прогона
- **WHEN** завершён train/eval цикл на очередной версии датасета
- **THEN** результаты MUST быть сохранены по категориям задач и использоваться для формирования backlog hard-cases следующей версии

### Requirement: Операционный профиль 1C-Expert-v4
Система MUST поддерживать профиль релизной сборки датасета `1C-Expert-v4` с целевым размером train-текста `500 MB .. 1 GB` и обязательным минимальным порогом `>= 200 MB`.

#### Scenario: Объём релиза ниже минимального порога
- **WHEN** pre-release проверка фиксирует размер train-текста меньше `200 MB`
- **THEN** релиз MUST быть заблокирован с явной причиной в отчёте

#### Scenario: Объём релиза в целевом диапазоне
- **WHEN** train-текст имеет размер в диапазоне `500 MB .. 1 GB`
- **THEN** релиз MAY продолжать pipeline без warning по объёму

### Requirement: Нормативный mix источников для 1C-Expert-v4
Система MUST обеспечивать mix источников в релизе `1C-Expert-v4`: `50%` реальный код 1C (BSL), `30%` общий coding-контур, `20%` RU identity-контур, с допустимым отклонением не более `5` процентных пунктов по каждому сегменту.

#### Scenario: Нарушение mix по сегментам
- **WHEN** фактическая доля любого сегмента выходит за пределы допустимого отклонения
- **THEN** релиз MUST быть заблокирован до коррекции состава датасета

#### Scenario: Mix соответствует профилю
- **WHEN** все сегменты находятся в пределах допустимого отклонения
- **THEN** система MUST фиксировать фактические доли в `manifest`/release-report

### Requirement: Гранулярность извлечения 1C-кода
Система MUST формировать 1C-сегмент датасета с гранулярностью "одна процедура или функция = один sample" на основе модулей минимум трёх типов: общие модули, модули менеджеров, модули объектов.

#### Scenario: Формирование sample из метода
- **WHEN** ingest обрабатывает исходный модуль 1C
- **THEN** каждая обнаруженная процедура/функция MUST экспортироваться отдельным sample, а не объединяться в монолитный блок

### Requirement: Контракт сериализации train-текста для RWKV
Система MUST сериализовать обучающие sample в plain text формате:
- префикс `Instruction:`;
- затем `Response:`;
- завершение каждого sample маркером `<|endoftext|>`.

Финальный train-текст MUST NOT содержать сырые сериализованные JSONL-объекты как рабочий формат sample.

#### Scenario: Проверка формата sample
- **WHEN** sample проходит форматный gate перед токенизацией
- **THEN** sample без `<|endoftext|>` или без пары `Instruction/Response` MUST быть отклонён

#### Scenario: Обнаружение сырого JSONL-текста
- **WHEN** в train-тексте обнаружены признаки не-нормализованного JSONL-объектного формата sample
- **THEN** релиз MUST быть заблокирован до исправления formatter-этапа

### Requirement: Обязательное перемешивание сегментов перед токенизацией
Система MUST выполнять interleave/shuffle sample из разных сегментов (`1C`, `coding`, `ru-identity`) перед запуском токенизации.

#### Scenario: Проверка порядка данных перед prepare_binidx
- **WHEN** сборка релиза завершает этап shuffle
- **THEN** итоговый порядок sample MUST быть перемешан между сегментами и зафиксирован в отчёте сборки

### Requirement: Базовые референсные датасеты для non-1C сегментов
Система MUST поддерживать baseline-allowlist внешних источников для профиля `1C-Expert-v4`:
- для `coding` сегмента: `MagicCoder-Evol-Instruct-110K`, `CodeAlpaca-20k`;
- для `ru-identity` сегмента: `saiga_scored`, `ru_turbo_alpaca`.

Замена или дополнение allowlist MUST сопровождаться документированным обоснованием качества и provenance.

#### Scenario: Добавление нового внешнего источника
- **WHEN** команда добавляет источник вне baseline-allowlist
- **THEN** система MUST требовать явное описание provenance и обоснование качества до включения источника в релиз

### Requirement: Trusted policy для локального repo-family корпуса
Система MUST относить к trusted/core контуру только deterministic sample, извлечённые из локального 1C source family без LLM-generated semantic enrichment.

#### Scenario: Детерминированный snapshot/history sample
- **WHEN** sample построен из snapshot BSL или локализуемого history diff без модельного перефразирования
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
- **WHEN** `attained_unique_volume_mb` после dedup ниже `volume.target_min_mb` общего dataset profile, но выше обязательного hard minimum
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

