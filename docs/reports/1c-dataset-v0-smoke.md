# Dataset v0 Report

- Dataset: `1c-dataset-v0-smoke`
- Version: `v0`
- Quality status: `PASS`
- Rows total: `10`

## Composition

- Splits: `{"eval_generation": 2, "eval_refactoring": 2, "train": 6}`
- Contours: `{"core": 6, "extended": 4}`
- Segments: `{"coding_general": 4, "onec_bsl": 4, "ru_identity": 2}`
- Categories: `{"code_generation": 4, "explanation_review": 1, "onec_query": 1, "refactoring": 4}`

## Quality Gates

- Quality reasons: `["quality gates passed"]`
- Gate metrics: `{"invalid_bsl_rows": 0, "invalid_eval_split_rows": 0, "invalid_ru_prompt_rows": 0, "invalid_schema_rows": 0, "secret_or_pii_rows": 0, "split_leakage_exact": 0, "split_leakage_near": 0, "train_category_distribution": {"code_generation": 2, "explanation_review": 1, "onec_query": 1, "refactoring": 2}}`

## Evaluation

- Overall verdict: `PASS`
- Domain eval: `{"notes": "Smoke holdout passed on dedicated generation/refactoring buckets.", "score": 0.82, "verdict": "PASS"}`
- Retention eval: `{"notes": "No retention regression beyond guardrail on smoke baseline.", "score": 0.8, "verdict": "PASS"}`

## Backlog Hard-Cases

- Hard cases total: `2`
- Hard cases by category: `{"code_generation": 1, "refactoring": 1}`
- [refactoring] missed side effects: Рефакторни длинную процедуру проведения документа. -> add more history-based 1C refactoring samples
- [code_generation] weak transaction boundary handling: Напиши менеджерский модуль для пакетного проведения документов. -> add more manager-module generation samples with transactional context
