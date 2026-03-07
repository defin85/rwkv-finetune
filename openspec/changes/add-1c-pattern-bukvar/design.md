## Context
Подготовка сильного reviewer-curated 1C корпуса требует не только source ingest и batch workflow, но и устойчивого “словаря смыслов”: какие инженерные принципы и 1C-паттерны мы считаем важными, как мы отличаем переносимый паттерн от конфигурационно-специфичного куска кода и на каких источниках строим это решение.

Проведённое исследование уже даёт качественную основу:
- `kb.1ci.com` — primary и наиболее надёжный источник platform-accurate правил и терминологии;
- `its.1c.ru` — русскоязычный прикладной слой с типовыми приёмами, удобный для примеров и operational guidance;
- книга Радченко/Хрусталёвой — хороший структурирующий источник тем для стартового каталога:
  - оптимизация проведения;
  - запросы и работа с виртуальными/временными таблицами;
  - оперативное/неоперативное проведение;
  - формы, команды, параметры, безмодальность;
  - базовая объектная модель встроенного языка.

При этом важно не превратить reference-источники в bulk train-corpus. Для этой задачи нужен отдельный артефакт уровня `rubric/букварь`, который будет служить входом в curator workflow и guide для reviewer-curated batches.

## Contract (Inputs / Outputs / Invariants)
- Inputs:
  - ссылки или локальные snapshots страниц `kb.1ci.com`;
  - локальные exports ИТС, полученные допустимым способом;
  - исследовательские заметки по книгам/пособиям;
  - локальные code exemplars из repo family;
  - notes по общим инженерным принципам, если они адаптированы к 1C.
- Outputs:
  - versioned `bukvar_manifest`;
  - набор `pattern_card` v1;
  - source manifest/evidence index для pattern cards;
  - mapping из pattern cards в curator workflow (`sample_class_mapping`, `search_cues`).
- Invariants:
  - букварь НЕ является train-corpus;
  - каждая pattern card MUST иметь source evidence;
  - каждая pattern card MUST содержать не только принцип, но и `1c_adaptation_note`;
  - каждая pattern card MUST указывать границы применимости (`when_not_to_apply`);
  - long-form reference text MUST NOT использоваться как bulk train payload.

## Goals / Non-Goals
- Goals:
  - Ввести versioned опорный артефакт для reviewer-curated 1C разметки.
  - Зафиксировать source hierarchy и evidence policy для pattern extraction.
  - Свести общие инженерные принципы и 1C-specific практики в один согласованный rubric.
  - Сделать curator workflow воспроизводимым между разными batch.
- Non-Goals:
  - Не собирать в этом change сам reviewer-curated train-corpus.
  - Не автоматизировать генерацию sample из reference-текста.
  - Не вводить новый contour данных поверх `core/extended`.
  - Не заменять `kb.1ci.com` ИТС или книгами в роли primary normative source.

## Decisions
- Decision: Ввести отдельный versioned `1C pattern букварь`, а не смешивать rules/rubric с dataset builder logic.
  - Rationale: curator workflow и dataset assembly уже являются отдельными capability; букварь должен быть их стабильным входом.

- Decision: Использовать иерархию источников с разными evidence tiers.
  - `normative_primary`: `kb.1ci.com`
  - `practical_supporting`: `its.1c.ru` export
  - `conceptual_supporting`: книги/пособия
  - `code_exemplars`: локальный repo family
  - Rationale: это минимизирует конфликты между источниками и соответствует repo policy для 1C documentation.

- Decision: Делать pattern cards не только 1C-specific, но и `general_principle -> 1C projection`.
  - Примеры:
    - батчевое чтение данных вместо лишних обращений через точку;
    - разделение фаз проведения документа;
    - корректные транзакционные и остаточные проверки;
    - безмодальный пользовательский сценарий;
    - distinction `ссылка / объект / выборка / набор записей`.
  - Rationale: это даёт переносимый reasoning signal вместо зубрёжки локальной конфигурации.

- Decision: Требовать у каждой pattern card поля `when_to_apply` и `when_not_to_apply`.
  - Rationale: паттерн без decision boundary ведёт к шаблонному и догматическому обучению.

- Decision: Для каждой pattern card фиксировать `search_cues` и `sample_class_mapping`.
  - `search_cues` нужны для поиска живых реализаций в repo family.
  - `sample_class_mapping` нужен для связи с `pattern_generation`, `pattern_refactor`, `pattern_review`, `pattern_explanation`.

- Decision: Ограничить scope `v1` стартовым каталогом pattern families из проведённого исследования.
  - Минимальный набор:
    - data access и object model;
    - query/performance;
    - document posting и остаточные проверки;
    - forms/commands/parameters;
    - modal-less and selection workflows.
  - Rationale: это самые богатые и уже подтверждённые темы по доступным источникам.

- Decision: Запретить использование reference-text как сырого bulk train-content.
  - Допустимо:
    - короткие цитатные note;
    - summary/rationale;
    - source refs и anchors.
  - Недопустимо:
    - массовое копирование учебных фрагментов в train-set.

## Risks / Trade-offs
- Риск: букварь станет слишком абстрактным и оторвётся от реального 1C-кода.
  - Mitigation: обязательные `code_exemplars` и `search_cues` на уровне pattern card.

- Риск: supporting-источники начнут противоречить normative source.
  - Mitigation: явный evidence tier и правило, что при конфликте приоритет у `kb.1ci.com`.

- Риск: букварь превратится в “конспект книги”, а не curator rubric.
  - Mitigation: обязательные поля `1c_adaptation_note`, `when_not_to_apply`, `sample_class_mapping`.

- Риск: общие инженерные принципы будут перенесены в 1C догматически.
  - Mitigation: pattern cards MUST описывать 1C adaptation и границы применимости, а не “чистую” чужую школу дизайна.

## Migration Plan
1. Зафиксировать contract `bukvar_manifest` и `pattern_card`.
2. Зафиксировать source hierarchy и evidence policy.
3. Зафиксировать initial v1 pattern families из проведённого исследования.
4. Зафиксировать handoff к reviewer-curated workflow через stable `pattern_id`, `search_cues` и `sample_class_mapping`.
5. Подготовить implementation-ready tasks для реальной сборки `букваря v0.1`.

## Open Questions
- Нужно ли в `v1` фиксировать количественный target по числу pattern cards или достаточно зафиксировать pattern families и acceptance criteria?
- Нужен ли в `v1` отдельный machine-readable export pattern cards помимо human-readable формата?
