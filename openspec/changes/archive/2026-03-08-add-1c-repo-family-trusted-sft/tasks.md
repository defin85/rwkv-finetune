## 1. Контракты source family и trust boundary
- [x] 1.1 Зафиксировать `repo_family_manifest` для локального 1C source family: `source_family_id`, `repo_roots[]`, `canonical_snapshot_root`, `training_permission`, `usage_policy`, `license/origin_ref`.
- [x] 1.2 Зафиксировать допустимые trusted sample-классы v1 как BSL-only `snapshot_method` и `history_method_change`, плюс явные exclusion rules для synthetic/LLM-enriched sample.
- [x] 1.3 Зафиксировать исключение `.epf`-связанных BSL-модулей из trusted v1.
- [x] 1.4 Зафиксировать fail-closed правила при отсутствии manifest, permission или provenance.

## 2. Snapshot ingest и канонизация
- [x] 2.1 Зафиксировать правила snapshot ingest из нескольких sibling-репозиториев одного family.
- [x] 2.2 Зафиксировать exact overlap detection и canonicalization до расчёта объёма.
- [x] 2.3 Зафиксировать policy обработки конфликтов по одинаковым путям с разным содержимым между sibling snapshot.

## 3. Git history ingest
- [x] 3.1 Зафиксировать контракт history-derived ingest для локализуемых BSL-изменений.
- [x] 3.2 Зафиксировать критерии отбора history commits и причины skip для слишком широких/шумных изменений.
- [x] 3.3 Зафиксировать provenance lineage для before/after sample и связь с commit metadata.

## 4. Split, leakage control и volume accounting
- [x] 4.1 Зафиксировать historical split policy для одного source family: sibling repos MUST NOT использоваться как независимые split boundaries.
- [x] 4.2 Зафиксировать, что для первого релиза temporal/lineage split + near-dedup обязателен, а отдельный task-family holdout не требуется.
- [x] 4.3 Зафиксировать exact/near dedup и leakage checks между snapshot/history/train/dev/eval слоями.
- [x] 4.4 Зафиксировать release-report по `attained_unique_volume_mb`, overlap/conflict статистике и deficit относительно `target_min_mb` из общего dataset profile.
- [x] 4.5 Зафиксировать hard minimum gate для trusted repo-family release и fail-closed поведение ниже порога.

## 5. Интеграция с текущей dataset-стратегией
- [x] 5.1 Зафиксировать, как trusted repo-family corpus попадает в `core`/`onec_bsl` контур как BSL-only источник, не ломая существующие provenance и quality gates.
- [x] 5.2 Зафиксировать зависимость и границы с `add-1c-multisource-corpus-assembly`, чтобы локальный repo family не дублировал общий ingest-контур.
- [x] 5.3 Зафиксировать, что реализация pilot release не использует final holdout для обучения и не добивает размер synthetic filler-данными.

## 6. Верификация и документация
- [x] 6.1 Добавить schema/tests для `repo_family_manifest`, canonicalization и overlap reporting.
- [x] 6.2 Добавить tests для history-derived filtering и split leakage control.
- [x] 6.3 Обновить документацию по intake локальных 1C репозиториев, permission metadata и pilot release workflow.

## 7. Зависимости выполнения
- [x] 7.1 Блок 1 MUST быть завершён до блоков 2-5.
- [x] 7.2 Блок 2 MUST быть завершён до финального volume accounting из блока 4.
- [x] 7.3 Блок 3 MUST быть завершён до leakage validation блока 4.
- [x] 7.4 Блоки 4-6 MUST быть завершены до pilot release handoff.
