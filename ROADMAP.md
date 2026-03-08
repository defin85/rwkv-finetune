Судя по текущим delta-spec'ам, делать это одной линейкой не стоит. Правильнее думать так: есть общий фундамент, потом две датасетные ветки, и отдельно оркестрация.

  Рекомендованный порядок

  1. add-1c-dataset-strategy
  2. add-1c-expert-v4-dataset-profile
  3. add-1c-repo-family-trusted-sft
  4. add-1c-multisource-corpus-assembly
  5. add-1c-pattern-bukvar
  6. add-1c-review-curated-pattern-corpus
  7. add-swe-rebench-v2-extended-source
  8. add-airflow-identity-hotfix-workflow отдельным параллельным потоком

  Почему именно так
  add-1c-dataset-strategy должен быть первым, потому что именно он задаёт базовый lifecycle, core/extended, RU-only policy и канонический контракт user_prompt / assistant_response + metadata spec.md:14
  spec.md:32. Без этого остальные change'и будут фиксировать частные форматы раньше общей модели.

  add-1c-expert-v4-dataset-profile идёт сразу после стратегии, потому что он задаёт operational constraints релиза: mix 50/30/20, формат Instruction/Response + <|endoftext|>, shuffle и allowlist внешних non-1C
  источников spec.md:14 spec.md:32 spec.md:55. Это контракт потребителя; источники должны под него подстраиваться, а не наоборот.

  add-1c-repo-family-trusted-sft логично идёт следующим как первый реальный 1C-source path. Он уже завершён и даёт deterministic core baseline с repo_family_manifest, canonicalization и leakage/split policy
  spec.md:3 spec.md:3. Это хороший “жёсткий” фундамент до semantic curation.

  После этого ветка делится.

  add-1c-multisource-corpus-assembly нужен раньше SWE-rebench, потому что он закрывает основной дефицит onec_bsl-сегмента и прямо интегрируется в 1C-Expert-v4 как источник onec_bsl spec.md:64. Это продолжение
  core-линии.

  add-1c-pattern-bukvar должен идти раньше add-1c-review-curated-pattern-corpus, потому что букварь публикует pattern_id, search_cues и sample_class_mapping как стабильный входной контракт для reviewer batches
  spec.md:48. Если сначала делать reviewer-curated, получится ad-hoc разметка без устойчивой таксономии.

  Только после букваря имеет смысл add-1c-review-curated-pattern-corpus: он уже сможет опираться и на trusted baseline из repo family, и на стабильные pattern cards. Сейчас у него есть важный пробел: в
  обязательных metadata перечислены curation_mode, source_family_id, source_file_ref, reviewer_rationale, generalization_note, но нет pattern_id tasks.md:6. Это стоит исправить до реализации.

  add-swe-rebench-v2-extended-source я бы отложил до стабилизации 1C-линии. Он зависит только от общей стратегии и профиля, живёт в extended/coding_general и не разблокирует onec_bsl spec.md:3.

  add-airflow-identity-hotfix-workflow не надо ставить в эту же очередь вообще. Он затрагивает только airflow-orchestration и решает отдельную runtime-задачу быстрого real-train identity gate proposal.md:18.
  Его можно делать параллельно, если нужен быстрый feedback loop по обучению.

  Что я бы поправил до старта реализации
  add-1c-multisource-corpus-assembly сейчас местами нормализует данные прямо в instruction/response на ingest-слое spec.md:24, а стратегия требует сначала канонический user_prompt / assistant_response, и
  только потом profile formatter spec.md:32. Это надо выровнять.

  Итого, если коротко: сначала общий dataset contract, потом release profile, потом deterministic 1C sources, потом rubric для semantic curation, потом reviewer-curated layer, и только после этого внешнее
  расширение coding_general. Airflow hotfix держать отдельно.