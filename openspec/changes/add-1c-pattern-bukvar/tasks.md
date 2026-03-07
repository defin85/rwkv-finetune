## 1. Scope и source policy
- [ ] 1.1 Зафиксировать, что `1C pattern букварь` является curator/rubric artifact, а не train-corpus.
- [ ] 1.2 Зафиксировать source hierarchy и evidence tiers: `kb.1ci.com`, ИТС export, книги/пособия, локальные code exemplars.
- [ ] 1.3 Зафиксировать правило разрешения конфликтов источников: при конфликте приоритет у `kb.1ci.com`.

## 2. Контракты артефактов
- [ ] 2.1 Зафиксировать contract `bukvar_manifest` с versioning и source manifest.
- [ ] 2.2 Зафиксировать contract `pattern_card`.
- [ ] 2.3 Зафиксировать обязательные поля `pattern_card`: `pattern_id`, `title`, `general_principle`, `1c_adaptation_note`, `when_to_apply`, `when_not_to_apply`, `positive_signals`, `anti_patterns`, `search_cues`, `sample_class_mapping`, `source_refs`, `evidence_tier`.

## 3. Pattern taxonomy v1
- [ ] 3.1 Зафиксировать стартовые pattern families на основе проведённого исследования.
- [ ] 3.2 Зафиксировать policy `general principle -> 1C projection` для pattern cards.
- [ ] 3.3 Зафиксировать, что pattern cards MUST описывать decision boundary, а не только “правильный шаблон”.

## 4. Интеграция с curator workflow
- [ ] 4.1 Зафиксировать handoff от букваря к `add-1c-review-curated-pattern-corpus` через stable `pattern_id`.
- [ ] 4.2 Зафиксировать `sample_class_mapping` для `pattern_generation`, `pattern_refactor`, `pattern_review`, `pattern_explanation`.
- [ ] 4.3 Зафиксировать, что `search_cues` используются для поиска exemplars в локальном repo family, а не заменяют file review.

## 5. Quality, provenance и copyright policy
- [ ] 5.1 Зафиксировать, что reference-text используется только как rubric/evidence layer, а не как bulk train-content.
- [ ] 5.2 Зафиксировать требования к provenance и citation notes для pattern cards.
- [ ] 5.3 Зафиксировать acceptance criteria для `букваря v1`: auditability, reproducibility, traceable source refs.

## 6. План первого релиза
- [ ] 6.1 Описать минимальный deliverable `букваря v0.1`.
- [ ] 6.2 Описать dependency/handoff с changes `add-1c-review-curated-pattern-corpus` и `add-1c-multisource-corpus-assembly`.
- [ ] 6.3 Валидировать change командой `openspec validate add-1c-pattern-bukvar --strict --no-interactive`.
