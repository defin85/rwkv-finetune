## 1. Контракт источника и staging
- [ ] 1.1 Зафиксировать local staging path и source manifest для `nebius/SWE-rebench-V2`.
- [ ] 1.2 Зафиксировать, что `v1` использует только issue-based corpus и не включает `SWE-rebench-V2-PRs`.
- [ ] 1.3 Зафиксировать fail-closed rules при отсутствии snapshot, manifest или обязательных provenance полей.

## 2. Eligibility и provenance
- [ ] 2.1 Зафиксировать обязательные instance-level поля `instance_id`, `repo`, `base_commit`, `problem_statement`, `patch`, `license`, `FAIL_TO_PASS`.
- [ ] 2.2 Зафиксировать сохранение `test_patch`, `PASS_TO_PASS`, `interface`, `meta`, `origin_ref`, `snapshot_ref` в metadata/release-report.
- [ ] 2.3 Зафиксировать exclusion reasons и отчёт по отфильтрованным instance.

## 3. Derived sample policy
- [ ] 3.1 Зафиксировать каноническую normalisation policy из task row в `user_prompt`/`assistant_response`.
- [ ] 3.2 Зафиксировать обязательный русский `user_prompt` и сохранение исходного английского текста с translation provenance.
- [ ] 3.3 Зафиксировать, что raw task row и raw execution logs не могут публиковаться как train sample без derived normalisation.
- [ ] 3.4 Зафиксировать, что raw unified diff не является обязательным универсальным target-форматом релиза.

## 4. Интеграция с контуром и профилем
- [ ] 4.1 Зафиксировать placement `SWE-rebench-V2` только в `extended/coding_general`.
- [ ] 4.2 Зафиксировать release cap `<= 50%` сегмента `coding_general` для первого релиза с этим источником.
- [ ] 4.3 Зафиксировать связь с allowlist/update policy профиля `1C-Expert-v4`.

## 5. Верификация и документация
- [ ] 5.1 Добавить schema/tests для source manifest, eligibility filter и metadata completeness.
- [ ] 5.2 Добавить tests для языковой политики и derived sample normalisation.
- [ ] 5.3 Обновить документацию intake внешних staged SWE datasets и release-report полей.

## 6. Зависимости выполнения
- [ ] 6.1 Блоки 1-2 MUST быть завершены до блоков 3-4.
- [ ] 6.2 Блок 3 MUST быть завершён до release gating блока 4.
- [ ] 6.3 Блоки 4-5 MUST быть завершены до handoff implementation phase.
