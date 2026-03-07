## Context
В репозитории уже появляется deterministic trusted ingest для локального repo family, но пользовательская цель на следующем этапе принципиально иная: не массово извлечь код, а семантически прочитать файлы и собрать обучающий корпус вокруг типовых 1C-паттернов. Это reviewer-style curating, а не обычный parser/builder.

Такой корпус:
- дороже по токенам и времени;
- слабее по "strict trust" в сравнении с deterministic extraction;
- но сильнее по переносимому training signal.

Из этого следует важная граница: reviewer-curated corpus нельзя смешивать с `core trusted` как будто это тот же класс источника. Минимальный безопасный дизайн — оставить двухконтурную модель `core/extended` и ввести новый `curation_mode=review_curated` внутри `extended`.

## Contract (Inputs / Outputs / Invariants)
- Inputs:
  - `repo_family_manifest` уже поддерживаемого локального source family;
  - `curation_batch_manifest` со списком файлов/модулей на review;
  - локальные текстовые BSL/XML exports, доступные reviewer workflow;
  - policy/guide по generalization и redaction config-specific деталей.
- Outputs:
  - reviewer-curated dataset release в каноническом sample-контракте;
  - `coverage_report` по просмотренным файлам и статусу review;
  - sample-level manifest с provenance до файла/модуля/lineage и reviewer rationale.
- Invariants:
  - curated sample MUST принадлежать `extended/onec_bsl`;
  - каждый sample MUST быть привязан к хотя бы одному просмотренному файлу;
  - sample MUST содержать pattern-level rationale, а не только ответ;
  - sample MUST быть переносимым за пределы конкретной конфигурации;
  - bulk deterministic extraction не заменяет reviewer-curated workflow.

## Goals / Non-Goals
- Goals:
  - Ввести workflow пофайлового reviewer curation для локального repo family.
  - Получать переносимые 1C-pattern sample вместо обучения на конкретной конфигурации.
  - Сохранить provenance и coverage, чтобы curated corpus оставался аудитируемым.
  - Ограничить scope v1 минимально необходимыми sample-классами и batch workflow.
- Non-Goals:
  - Не заменять и не удалять `core trusted` deterministic corpus.
  - Не превращать workflow в fully automatic generator pipeline.
  - Не добавлять execution-based SWE training.
  - Не вводить третий contour вместо уже принятой модели `core/extended`.

## Decisions
- Decision: Оставить reviewer-curated corpus внутри `extended`, а не вводить новый contour.
  - Rationale: это минимально конфликтует с уже принятым change `add-1c-dataset-strategy`.

- Decision: Ввести `curation_batch_manifest` как основной intake unit вместо "просканировать весь репозиторий разом".
  - Rationale: reviewer-style curation дорог по лимитам; batching нужен для управляемости, coverage и воспроизводимости.

- Decision: Требовать file-by-file review как обязательное условие curated sample.
  - Rationale: смысл change именно в semantic inspection файлов, а не в автоматическом парсинге.

- Decision: Определить curated sample как pattern-oriented, а не configuration-oriented.
  - Допустимые классы v1:
    - `pattern_generation`
    - `pattern_refactor`
    - `pattern_review`
    - `pattern_explanation`
  - Rationale: эти классы хорошо ложатся на уже принятые категории задач и позволяют извлекать reusable signal.

- Decision: Ввести обязательную generalization policy для sample.
  - Примеры допустимого обобщения:
    - паттерн проведения документа;
    - паттерн построения запроса;
    - паттерн валидации и guard clauses;
    - smell длинной процедуры и refactoring path.
  - Примеры недопустимого target:
    - обучение конкретным бизнес-сущностям конфигурации без переноса на общий 1C-контекст;
    - sample, где ценность определяется только уникальным названием объекта/регистра.

- Decision: Требовать reviewer rationale и source refs на уровне каждого sample.
  - Rationale: curated sample должен быть проверяем по происхождению и по смысловому выводу reviewer.

- Decision: Не считать raw bulk extraction реализацией этого change.
  - Rationale: этот change нужен именно для semantic curation, а не для очередного parser-driven pass.

## Risks / Trade-offs
- Риск: reviewer-curated workflow дорог по токенам и времени.
  - Mitigation: batching, coverage tracking, ограничение числа sample на файл и явный backlog.

- Риск: curated sample будут слишком завязаны на локальный бизнес-контекст.
  - Mitigation: обязательная generalization note и exclusion policy для непереносимых кейсов.

- Риск: слабая воспроизводимость "ручного" curating.
  - Mitigation: curation manifests, reviewer rationale, coverage reports и versioned release artifacts.

- Риск: смешение reviewer-curated данных с strict trusted core.
  - Mitigation: отдельное placement в `extended` и явный `curation_mode=review_curated`.

## Migration Plan
1. Зафиксировать batch manifest и coverage report contracts.
2. Зафиксировать sample schema и pattern taxonomy для reviewer-curated корпуса.
3. Зафиксировать policy generalization/decontextualization.
4. Зафиксировать placement в `extended/onec_bsl` и release reporting.
5. Подготовить implementation-ready tasks для incremental curation batches.

## Open Questions
- Какой стартовый размер `curation_batch_manifest` считать практичным для v1: десятки файлов или сотни?
- Нужно ли в v1 ограничивать число curated sample на один файл, чтобы не перегружать корпус повторами одного паттерна?
