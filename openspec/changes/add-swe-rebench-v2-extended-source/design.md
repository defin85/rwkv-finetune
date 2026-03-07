## Context
Текущий `rwkv-finetune` строит датасет для RWKV через канонический контракт `user_prompt`/`assistant_response` и профильную сериализацию в `Instruction/Response`. Non-1C сегмент `coding_general` пока ориентирован на готовые instruction/code datasets, которые уже близки к SFT-формату.

`SWE-rebench-V2` находится на другом уровне:
- source row содержит task instance, а не готовый train sample;
- исходный natural-language слой англоязычный;
- в строке есть rich provenance и execution-support поля (`repo`, `base_commit`, `patch`, `test_patch`, `FAIL_TO_PASS`, `PASS_TO_PASS`, `install_config`, `interface`, `meta`);
- этот источник полезен как future-derived SFT source, но не как drop-in replacement для текущего builder.

Практический вывод для этого change: в репозитории нужен не execution-runtime контракт, а контракт staged ingest + curating + derived SFT normalisation.

## Contract (Inputs / Outputs / Invariants)
- Inputs:
  - локальный snapshot `nebius/SWE-rebench-V2` в дереве `data/external/reference_datasets/1c-expert-v4/`;
  - source manifest со значениями `dataset_id`, `snapshot_ref`, `origin_ref`, `dataset_license`, `source_kind=issue_based`;
  - rows issue-based task instances с полями `instance_id`, `repo`, `base_commit`, `problem_statement`, `patch`, `test_patch`, `FAIL_TO_PASS`, `PASS_TO_PASS`, `interface`, `license`, `meta`.
- Outputs:
  - derived sample для `extended/coding_general` в каноническом формате `user_prompt`/`assistant_response`;
  - release-report с inclusion/exclusion статистикой, translation provenance, license breakdown и долей источника в `coding_general`;
  - sample-level metadata с исходными task fields для аудита и будущих execution-oriented итераций.
- Invariants:
  - build-stage ingest работает только с локальным snapshot и MUST NOT зависеть от сети;
  - `v1` использует только `nebius/SWE-rebench-V2` issue-based corpus и MUST NOT включать `SWE-rebench-V2-PRs`;
  - source размещается только в `extended` и MUST NOT попадать в `core`;
  - train/eval допускают только русскоязычный `user_prompt`, оригинальный английский текст сохраняется в metadata;
  - raw task row MUST NOT публиковаться как train sample без derived normalisation;
  - этот change не вводит Docker/execution runtime и MUST NOT требовать тестового исполнения задач на этапе ingest.

## Goals / Non-Goals
- Goals:
  - Зафиксировать staged ingest будущего `SWE-rebench-V2` без размывания текущего SFT-пайплайна.
  - Сохранить полный instance-level provenance и repo-license по каждому derived sample.
  - Нормализовать issue-based tasks в безопасный для RWKV SFT формат с русскоязычным `user_prompt`.
  - Ограничить долю нового источника в первых релизах, чтобы не размыть `coding_general`.
- Non-Goals:
  - Не добавлять execution-based SWE training, Docker runner или reward loop.
  - Не включать в `v1` PR-корпус `SWE-rebench-V2-PRs`.
  - Не переводить источник в `core` contour.
  - Не делать raw unified diff универсальным target-форматом для всего релиза.

## Decisions
- Decision: Использовать только локально staged snapshot `SWE-rebench-V2`.
  - Rationale: совпадает с уже принятой практикой `data/external/reference_datasets/...` и сохраняет воспроизводимость релиза.

- Decision: Ограничить `v1` issue-based corpus `nebius/SWE-rebench-V2` и исключить `SWE-rebench-V2-PRs`.
  - Rationale: issue-based subset лучше соответствует реальному problem statement и даёт более чистый сигнал для derived SFT.
  - Alternatives considered:
    - включить PR corpus сразу: даёт больше объёма, но повышает риск leakage и synthetic/noisy statements.

- Decision: Классифицировать `SWE-rebench-V2` только как `extended/coding_general`.
  - Rationale: per-instance repo licenses mixed, а сам источник не является 1C-specific core knowledge.

- Decision: Требовать русскоязычный `user_prompt` и сохранять оригинальный `problem_statement` в metadata вместе с полями translation provenance.
  - Rationale: это сохраняет соответствие глобальной языковой политике без потери трассировки к исходной задаче.

- Decision: Derived train sample MUST быть нормализованным SFT sample, а не raw task row.
  - Допустимая форма v1:
    - русскоязычный prompt с кратким описанием проблемы и ограничений задачи;
    - fix-oriented `assistant_response`, полученный из gold solution без включения сырых логов исполнения.
  - Поля `patch`, `test_patch`, `FAIL_TO_PASS`, `PASS_TO_PASS`, `interface`, `meta` сохраняются в metadata/provenance.
  - Rationale: builder и профиль релиза работают с SFT sample, а не с execution tasks.

- Decision: Для `v1` ввести release cap `<= 50%` сегмента `coding_general`.
  - Rationale: новый источник должен усиливать, а не вытеснять уже понятные coding datasets.

- Decision: Instance eligibility делать fail-closed по обязательным полям.
  - Обязательные поля:
    - `instance_id`
    - `repo`
    - `base_commit`
    - `problem_statement`
    - `patch`
    - `license`
    - `FAIL_TO_PASS`
  - Rationale: без этих полей теряется provenance или задача перестаёт быть достаточно проверяемой как derived source.

## Risks / Trade-offs
- Риск: перевод `problem_statement` на русский внесёт смысловые искажения.
  - Mitigation: хранить original text, translation provenance и exclusion reason для неустойчивых случаев.

- Риск: модель начнёт переучиваться на patch-style ответы.
  - Mitigation: не использовать raw diff как единственный target-формат и ограничить долю источника в `coding_general`.

- Риск: legal/policy ambiguity из-за mixed repo licenses.
  - Mitigation: держать источник в `extended`, сохранять instance-level license и блокировать строки без license/provenance.

- Риск: путаница между dataset ingest и execution-based runtime capability.
  - Mitigation: явная граница scope: no Docker/no test execution/no reward loop в этом change.

## Migration Plan
1. Зафиксировать source contract, staging path и eligibility rules для `SWE-rebench-V2`.
2. Зафиксировать canonical derived sample policy и translation provenance.
3. Зафиксировать placement в `extended/coding_general` и release cap для первого релиза.
4. Зафиксировать allowlist/update policy и release reporting.
5. Подготовить implementation-ready tasks без включения execution runtime.

## Open Questions
- Нужно ли в будущей реализации поддерживать один derived target-формат или отдельные подтипы (`repair_plan`, `fix_response`, `review_summary`) внутри одного source?
- Следует ли позже разрешить небольшой opt-in subtrack с patch-centric target, если он будет явно размечен отдельно от основного `coding_general` потока?
