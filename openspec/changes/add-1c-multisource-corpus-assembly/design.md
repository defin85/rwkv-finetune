## Context
Нужно собирать объёмный 1C core корпус (`300 MB .. 1 GB`) не из одного источника BSL, а из трёх независимых потоков:
- экспорт конфигурации 1C;
- выгрузка синтаксис-помощника;
- контент `kb.1ci.com`.

Текущий builder работает с BSL + внешними JSONL сегментами и не фиксирует единый ingest-контракт для этих трёх 1C-источников.

## Contract (Inputs / Outputs / Invariants)
- Inputs:
  - `onec_config_export` (локальный экспорт модулей 1C);
  - `syntax_helper_export` (локальная выгрузка синтаксис-помощника);
  - `kb1c_snapshot` (локальный snapshot страниц `kb.1ci.com`).
- Outputs:
  - merged 1C core corpus в каноническом sample-контракте `user_prompt` / `assistant_response` + metadata;
  - release-report/manifest с provenance, лицензиями, метриками качества и объёма.
- Invariants:
  - для каждого sample обязательны provenance и license поля;
  - `kb`-контур ограничен доменом `kb.1ci.com`;
  - merged core stage MUST оставаться profile-agnostic и MUST NOT фиксировать `Instruction/Response + <|endoftext|>` как внутренний ingest-контракт;
  - fail-closed при нарушении schema, источниковых контрактов или quality gates.

## Goals / Non-Goals
- Goals:
  - Сделать воспроизводимый ingest трёх 1C-источников в общий core корпус.
  - Стабилизировать качество и объём core корпуса перед этапом mix в `1C-Expert-v4`.
  - Обеспечить трассируемость каждого sample до источника.
  - Сохранить совместимость с общей dataset strategy: канонический sample-контракт на ingest-слое и отдельная profile serialization на release-слое.
- Non-Goals:
  - Редизайн всего train/eval оркестратора Airflow.
  - Замена текущего профиля `1C-Expert-v4` или базового mix-подхода.
  - Перенос profile formatter-логики внутрь source adapters или merged core ingest stage.

## Decisions
- Decision: Ввести двухступенчатую сборку `source adapters -> merged 1C core -> profile mix`.
  - Rationale: отделяет качество 1C-контента от последующего смешивания с non-1C сегментами.
- Decision: Держать merged 1C core corpus в каноническом sample-контракте `user_prompt` / `assistant_response` + metadata до profile layer.
  - Rationale: это согласует change с `add-1c-dataset-strategy` и не смешивает source-ingestion с profile serialization.
- Decision: Принять только локальные выгрузки/снимки как вход адаптеров.
  - Rationale: повышает воспроизводимость и снижает runtime-зависимость от внешних сайтов.
- Decision: Для `kb`-контента применять доменную политику allowlist (`kb.1ci.com`) и фиксировать `origin_ref`.
  - Rationale: ограничение легитимного источника и контроль provenance.
- Decision: Ввести отдельный объёмный gate `300 MB .. 1 GB` для merged 1C core корпуса.
  - Rationale: соответствует целевому диапазону для практического дообучения перед полным mix.

## Risks / Trade-offs
- Форматы выгрузок синтаксис-помощника могут отличаться между версиями/инструментами.
  - Mitigation: версионированный контракт форматов + явные adapter errors.
- Контент документации может содержать много объяснительного текста и мало кода.
  - Mitigation: классификация sample по типам + квоты/отчёт по источниковому вкладу.
- Жёсткий объёмный gate может блокировать релиз на ранних итерациях curating.
  - Mitigation: отдельный отчёт дефицита и список недостающих источниковых объёмов.

## Migration Plan
1. Зафиксировать contracts/schema для трёх источников и manifest.
2. Добавить source adapters и нормализацию в канонический sample-контракт.
3. Добавить merged-stage quality gates и volume gate.
4. Подключить merged core корпус к профилю `1C-Expert-v4` через profile formatter/export adapter.
4. Обновить документацию и smoke-процедуру.

## Open Questions
- Точный формат выгрузки синтаксис-помощника (JSON/XML/HTML/другое) для первого релиза.
- Политика включения контента `kb.1ci.com`: только code-примеры или также объяснительные блоки.
- Целевая доля вкладов `config/syntax/kb` внутри 1C core корпуса для v1.
