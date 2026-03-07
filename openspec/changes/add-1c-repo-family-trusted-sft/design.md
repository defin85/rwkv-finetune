## Context
Репозиторий уже фиксирует стратегию датасетов, quality gates и профиль `1C-Expert-v4`, но пока не описывает отдельный trusted ingest-контур для локального family 1C-репозиториев с глубокой git-историей. Практический кейс текущей задачи: два локальных git-репозитория относятся к одной и той же конфигурации и не могут считаться независимыми источниками при оценке объёма или построении split.

Новый change нужен для того, чтобы превратить локальный family-источник в воспроизводимый trusted-контур без переоценки объёма и без leakage через "разные" репозитории, которые по факту почти совпадают по snapshot-состоянию.

## Contract (Inputs / Outputs / Invariants)
- Inputs:
  - `repo_family_manifest`:
    - `source_family_id`
    - `repo_roots[]`
    - `canonical_snapshot_root`
    - `training_permission`
    - `usage_policy`
    - `license`/`origin_ref` policy
  - локальные git-репозитории 1С с доступной историей;
  - локальные `conf_files`/metadata snapshot, если они входят в source family.
- Outputs:
  - trusted 1C corpus release в каноническом sample-контракте;
  - release-report с полями overlap, conflict, unique volume, split lineage и deficit относительно target;
  - machine-readable manifest по каждому sample и по family-level release.
- Invariants:
  - sibling-репозитории одного source family не считаются независимыми источниками при split;
  - trusted contour принимает только deterministic sample без LLM-generated enrichment;
  - объём trusted release считается только после exact/near dedup и overlap canonicalization;
  - при отсутствии permission/provenance/source-family manifest сборка завершается fail-closed.

## Goals / Non-Goals
- Goals:
  - Зафиксировать локальный 1C repo family как поддерживаемый trusted source.
  - Снизить риск leakage между train/dev/eval для репозиториев одной конфигурации.
  - Сделать volume accounting честным: считать только уникальный trusted объём после dedup.
  - Ввести воспроизводимый ingest git history как дополнительный trusted сигнал.
- Non-Goals:
  - Не добавлять execution-based SWE training в этом change.
  - Не вводить synthetic/LLM-enriched explanation samples в trusted contour v1.
  - Не заменять общий мульти-источниковый ingest для `config/syntax/kb`, а только дополнять его локальным family source.

## Decisions
- Decision: Рассматривать несколько локальных репозиториев одной конфигурации как один `source family`, а не как независимые источники.
  - Rationale: это устраняет ложное ощущение роста корпуса и снижает leakage через sibling snapshot/history.

- Decision: Ввести `canonical_snapshot_root` в family manifest.
  - Rationale: при почти полном overlap текущего состояния нужен предсказуемый источник canonical snapshot и детерминированная обработка конфликтов по одинаковым путям.

- Decision: В trusted contour v1 принимать только deterministic sample-классы.
  - Допустимые классы:
    - `snapshot_method`
    - `history_method_change`
    - `metadata_linked_context`, если он строится без LLM-перефразирования.
  - Исключения:
    - `.epf`-связанные BSL-модули не входят в trusted contour v1.
  - Rationale: это сохраняет доверие к target-содержимому и provenance.
  - Alternatives considered:
    - Добавить LLM-generated summaries/explanations сразу: быстрее добрать объём, но ухудшается trust boundary.

- Decision: Исторические sample извлекать только из локализуемых изменений.
  - Rationale: широкие коммиты с десятками файлов дают плохой supervised signal и высокий риск шумных before/after пар.
  - Пример критериев локализуемости:
    - ограниченное число BSL-файлов;
    - детерминированно выделяемый метод/фрагмент;
    - нет зависимости на бинарные артефакты как единственный meaningful diff.

- Decision: Train/dev/eval split внутри одного source family строить по времени и lineage, а не по имени репозитория.
  - Rationale: sibling-репозитории почти совпадают по текущему состоянию, поэтому split "по repo" не защищает от leakage.

- Decision: Для первого trusted release не требовать отдельный holdout по семействам задач/директорий.
  - Rationale: на старте достаточно temporal/lineage split + near-dedup контроля; дополнительный task-family holdout усложняет intake без достаточной пользы для v1.

- Decision: Целевой объём trusted release считать как `attained_unique_volume`, а не добивать synthetic filler до красивой цифры.
  - Rationale: для trusted contour важнее честная уникальность корпуса, чем номинальный размер.
  - Alternatives considered:
    - Жёстко требовать `1 GB` в trusted contour любой ценой: ведёт к скрытому раздуванию дубликатами или synthetic sample.

- Decision: Trusted repo-family corpus v1 MUST проходить обязательный hard minimum по уникальному объёму после dedup.
  - Rationale: pilot release должен быть не только честным по объёму, но и достаточно ёмким, чтобы иметь практическую ценность в `core` контуре.
  - Consequence: если `attained_unique_volume_mb` ниже hard minimum, trusted release блокируется и не публикуется как готовый `core` источник.

## Risks / Trade-offs
- Риск: фактический уникальный trusted объём после dedup окажется заметно меньше ожидаемого.
  - Mitigation: deficit reporting, отдельный `attained_unique_volume_mb`, fail-closed ниже hard minimum и решение о расширении источников после пилота.

- Риск: история коммитов содержит слишком много шумных или широких изменений.
  - Mitigation: strict filters на локализуемость history-derived sample и явная отчётность по skipped commits.

- Риск: sibling-репозитории имеют конфликтующие версии одинаковых путей.
  - Mitigation: canonical root + conflict report + policy явного выбора, а не silent merge.

- Риск: локальные репозитории являются внутренними источниками с отдельными usage restrictions.
  - Mitigation: обязательный `training_permission` и usage policy в family manifest.

## Migration Plan
1. Зафиксировать `repo_family_manifest` и trusted sample classes.
2. Добавить family-level canonicalization и overlap report для snapshot-слоя.
3. Добавить history extractor с фильтрами локализуемых изменений.
4. Подключить trusted repo family как источник `onec_bsl`/core-контуров без synthetic enrichment.
5. Выпустить pilot release с честным отчётом `attained_unique_volume_mb`, leakage checks и split lineage.
