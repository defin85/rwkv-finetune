## 1. Контракты intake и batching
- [ ] 1.1 Зафиксировать `curation_batch_manifest` для reviewer-curated workflow: `source_family_id`, список файлов/модулей, batch metadata, reviewer metadata.
- [ ] 1.2 Зафиксировать `coverage_report` по файлам и статусам review.
- [ ] 1.3 Зафиксировать fail-closed policy: sample без batch/file provenance не допускается.

## 2. Sample schema и taxonomy
- [ ] 2.1 Зафиксировать placement reviewer-curated sample в `extended/onec_bsl`.
- [ ] 2.2 Зафиксировать допустимые sample-классы v1: `pattern_generation`, `pattern_refactor`, `pattern_review`, `pattern_explanation`.
- [ ] 2.3 Зафиксировать обязательные metadata поля: `curation_mode`, `source_family_id`, `source_file_ref`, `reviewer_rationale`, `generalization_note`, `license`, `origin_ref`.

## 3. Generalization policy
- [ ] 3.1 Зафиксировать критерий переносимости: sample MUST обучать типичному 1C-паттерну, а не конкретной конфигурации.
- [ ] 3.2 Зафиксировать policy decontextualization/redaction для конфигурационно-специфичных сущностей.
- [ ] 3.3 Зафиксировать exclusion rules для непереносимых sample.

## 4. Workflow reviewer curation
- [ ] 4.1 Зафиксировать, что file-by-file review обязателен для каждого curated sample.
- [ ] 4.2 Зафиксировать, что raw bulk extraction не считается реализацией reviewer-curated workflow.
- [ ] 4.3 Зафиксировать incremental batch workflow для работы в рамках token budgets.

## 5. Верификация и release policy
- [ ] 5.1 Зафиксировать tests/schema validation для batch manifest, coverage report и curated sample metadata.
- [ ] 5.2 Зафиксировать release-report по coverage, excluded files/sample и pattern-type distribution.
- [ ] 5.3 Зафиксировать совместимость с текущим `1C-Expert-v4` mix без ослабления quality gates.

## 6. Документация
- [ ] 6.1 Описать reviewer workflow для локального repo family.
- [ ] 6.2 Описать критерии "переносимого паттерна" и anti-pattern примеры.
- [ ] 6.3 Описать handoff между `core trusted` и `review-curated extended`.

## 7. Зависимости выполнения
- [ ] 7.1 Блок 1 MUST быть завершён до блоков 2-5.
- [ ] 7.2 Блоки 2-3 MUST быть завершены до workflow правил блока 4.
- [ ] 7.3 Блоки 4-6 MUST быть завершены до implementation handoff.
