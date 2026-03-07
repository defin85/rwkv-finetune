# Change: Добавить versioned 1C pattern букварь для curator workflow

## Why
В репозитории уже появляются два важных слоя:
- deterministic trusted baseline из локального repo family;
- reviewer-curated pattern corpus из тех же локальных источников.

Но между ними пока отсутствует устойчивый опорный слой, который отвечает на вопрос: **какие именно переносимые 1C-паттерны и инженерные принципы мы хотим извлекать, как их адаптировать к 1C и на каких источниках это основано**.

Проведённое исследование показало, что полезные знания уже доступны, но они разрознены:
- `kb.1ci.com` даёт нормативный и platform-accurate контекст;
- русскоязычный ИТС даёт прикладные пояснения и типовые приёмы;
- книга Радченко/Хрусталёвой 2023 года даёт структурированный обзор практических тем: оптимизация проведения, формы, подборы, объектная модель встроенного языка;
- локальный repo family даёт живые кодовые реализации и вариации паттернов.

Без отдельного change остаются риски:
- reviewer-curated разметка будет зависеть от текущей памяти и стиля куратора;
- одни и те же паттерны будут формулироваться по-разному в разных batch;
- общие инженерные принципы будут переноситься в 1C непоследовательно;
- reference-источники могут начать использоваться как сырой train-text вместо rubric/evidence слоя.

## What Changes
- Добавляется capability versioned `1C pattern букваря` как отдельного curator artifact, а не как train-corpus.
- Фиксируется source hierarchy для подготовки букваря:
  - `kb.1ci.com` как primary normative source;
  - `its.1c.ru` export как supporting practical source;
  - отобранные книги/пособия как supporting conceptual source;
  - локальный repo family как source exemplars, а не как источник норматива.
- Фиксируется контракт `pattern_card` для букваря:
  - `pattern_id`, `title`, `general_principle`, `1c_adaptation_note`,
  - `when_to_apply`, `when_not_to_apply`,
  - `positive_signals`, `anti_patterns`,
  - `search_cues`, `sample_class_mapping`,
  - `source_refs`, `evidence_tier`.
- Фиксируется политика использования reference-text:
  - reference-источники используются для rubric, evidence и rationale;
  - длинные verbatim-фрагменты НЕ считаются train-output и НЕ должны служить bulk-корпусом.
- Фиксируется handoff от букваря к reviewer-curated workflow:
  - pattern cards должны быть stable и versioned;
  - curation batches должны ссылаться на `pattern_id`, а не только на “интуитивную тему”.
- Фиксируется минимальный scope `v1`:
  - короткий versioned букварь;
  - стартовый pattern catalog;
  - без автоматической генерации train-sample и без execution-based workflow.

## Impact
- Affected specs:
  - `dataset-curation-guidance`
- Related changes:
  - `add-1c-review-curated-pattern-corpus`
  - `add-1c-repo-family-trusted-sft`
  - `add-1c-multisource-corpus-assembly`
  - `add-1c-dataset-strategy`
- Affected code/docs:
  - versioned rubric/bukvar artifacts;
  - pattern-card schema и source policy;
  - документация handoff между reference research, local code exemplars и curator workflow.
