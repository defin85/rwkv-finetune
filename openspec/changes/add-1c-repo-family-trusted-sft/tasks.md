## 1. Контракты source family и trust boundary
- [ ] 1.1 Зафиксировать `repo_family_manifest` для локального 1C source family: `source_family_id`, `repo_roots[]`, `canonical_snapshot_root`, `training_permission`, `usage_policy`, `license/origin_ref`.
- [ ] 1.2 Зафиксировать допустимые trusted sample-классы v1 и явные exclusion rules для synthetic/LLM-enriched sample.
- [ ] 1.3 Зафиксировать исключение `.epf`-связанных BSL-модулей из trusted v1.
- [ ] 1.4 Зафиксировать fail-closed правила при отсутствии manifest, permission или provenance.

## 2. Snapshot ingest и канонизация
- [ ] 2.1 Зафиксировать правила snapshot ingest из нескольких sibling-репозиториев одного family.
- [ ] 2.2 Зафиксировать exact overlap detection и canonicalization до расчёта объёма.
- [ ] 2.3 Зафиксировать policy обработки конфликтов по одинаковым путям с разным содержимым между sibling snapshot.

## 3. Git history ingest
- [ ] 3.1 Зафиксировать контракт history-derived ingest для локализуемых BSL-изменений.
- [ ] 3.2 Зафиксировать критерии отбора history commits и причины skip для слишком широких/шумных изменений.
- [ ] 3.3 Зафиксировать provenance lineage для before/after sample и связь с commit metadata.

## 4. Split, leakage control и volume accounting
- [ ] 4.1 Зафиксировать historical split policy для одного source family: sibling repos MUST NOT использоваться как независимые split boundaries.
- [ ] 4.2 Зафиксировать, что для первого релиза temporal/lineage split + near-dedup обязателен, а отдельный task-family holdout не требуется.
- [ ] 4.3 Зафиксировать exact/near dedup и leakage checks между snapshot/history/train/dev/eval слоями.
- [ ] 4.4 Зафиксировать release-report по `attained_unique_volume_mb`, overlap/conflict статистике и deficit относительно target.
- [ ] 4.5 Зафиксировать hard minimum gate для trusted repo-family release и fail-closed поведение ниже порога.

## 5. Интеграция с текущей dataset-стратегией
- [ ] 5.1 Зафиксировать, как trusted repo-family corpus попадает в `core`/`onec_bsl` контур, не ломая существующие provenance и quality gates.
- [ ] 5.2 Зафиксировать зависимость и границы с `add-1c-multisource-corpus-assembly`, чтобы локальный repo family не дублировал общий ingest-контур.
- [ ] 5.3 Зафиксировать, что реализация pilot release не использует final holdout для обучения и не добивает размер synthetic filler-данными.

## 6. Верификация и документация
- [ ] 6.1 Добавить schema/tests для `repo_family_manifest`, canonicalization и overlap reporting.
- [ ] 6.2 Добавить tests для history-derived filtering и split leakage control.
- [ ] 6.3 Обновить документацию по intake локальных 1C репозиториев, permission metadata и pilot release workflow.

## 7. Зависимости выполнения
- [ ] 7.1 Блок 1 MUST быть завершён до блоков 2-5.
- [ ] 7.2 Блок 2 MUST быть завершён до финального volume accounting из блока 4.
- [ ] 7.3 Блок 3 MUST быть завершён до leakage validation блока 4.
- [ ] 7.4 Блоки 4-6 MUST быть завершены до pilot release handoff.
