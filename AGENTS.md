<!-- OPENSPEC:START -->

# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:

- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:

- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

# Язык (важно)

- Планы и спеки ведём на русском языке: OpenSpec (`openspec/specs/**`, `openspec/changes/**`) и описания задач/планов в процессе работы.
- Общепринятые термины, названия сущностей, API/эндпоинты, ключи настроек и code identifiers можно оставлять на английском, но общий смысл должен быть понятен без перевода.

# Unified Workflow

We operate in a cycle: **OpenSpec (What) → Beads (How) → Code (Implementation)**.

## 1. Intent Formation

The user initiates with:
`/openspec-proposal "Add 2FA authentication"`

OpenSpec creates a change folder (`openspec/changes/<change-id>/`) containing:

- `proposal.md`: Business value and scope.
- `tasks.md`: High-level task list.
- `design.md`: Technical design (optional).
- `specs/.../spec.md`: Requirements and acceptance criteria.

**Agent Goal**: Edit these files until they represent a signable contract.

**DO NOT proceed to step 2 until you are explicitly told the keyword "Go!" in English.**

## 2. Task Transformation

Once the change is approved, execute the agent command:
`/openspec-to-beads <change-id>`

The agent must:

1.  Read the change files.
2.  Create a Beads Epic for the feature. Include a short description summarizing the intent and referencing the change folder (e.g., "See openspec/changes/<change-id>/").
3.  Create Beads Tasks for each item in `tasks.md`. Include a brief description for each task to provide context (why this issue exists and what needs to be done).
4.  Set dependencies (e.g., Infra blocks Backend blocks Frontend).

Result: A **live task graph in `.beads/`**, not just text.

## 3. Execution

Work loop:

- `bd ready`: Check actionable tasks
- `bd show <task-id>`: Get task context
- Implement code
- `bd close <task-id>`: Complete task
- `bd sync`: Sync state

**Rule**: Only work on tasks listed in `bd ready`.

## 4. Fixation

When all tasks are complete, execute the agent commands:

- `/openspec-apply <change-id>`: Verify code meets specs.
- Then, when ready,
- `/openspec-archive <change-id>`: Archive the change.

---

## Agent Mental Checklist

1.  **Start**: Is there an active OpenSpec change?
    - No? → Create one (`/openspec-proposal`).
    - Yes? → Read `proposal.md` and `tasks.md`.
2.  **Plan**: Are tasks tracked in Beads?
    - No? → Generate graph (`/openspec-to-beads`).
    - Yes? → Work from `bd ready`.
3.  **Align**: Keep OpenSpec (Intent) ↔ Beads (Plan) ↔ Code (Reality) in sync.

---

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   - `git pull --rebase`
   - `bd sync`
   - `git push`
   - `git status` - MUST show "up to date with origin"
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**

- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds

## Issue Tracking

This project uses **bd (beads)** for issue tracking.
Run `bd prime` for workflow context.

**Quick reference:**

- `bd ready` - Find unblocked work
- `bd create "Title" --type task --priority 2 --description "..."` - Create ad-hoc issue
- `bd close <task-id>` - Complete work
- `bd sync` - Sync with git (run at session end)

For full workflow details: `bd prime`

### Beads sync-branch: “постоянно меняется .beads/issues.jsonl”

В этом репозитории Beads работает в режиме sync-branch (по умолчанию `sync-branch: beads-sync` в `.beads/config.yaml`).
В таком режиме `.beads/*.jsonl` часто меняются из-за daemon/auto-flush и **не должны** постоянно “грязнить” рабочее дерево
на ветках с кодом.

Если после коммита у вас регулярно появляется `M .beads/issues.jsonl`:

- Рекомендовано: `bd doctor --fix` (исправляет git index flags для Beads файлов).
- Быстрый ручной фикс (локально):
  - `git update-index --skip-worktree .beads/issues.jsonl .beads/interactions.jsonl .beads/config.yaml .beads/metadata.json`
- Откатить (если нужно снова видеть изменения):
  - `git update-index --no-skip-worktree .beads/issues.jsonl .beads/interactions.jsonl .beads/config.yaml .beads/metadata.json`

## Семантический поиск (claude-context)

При поиске по коду использовать следующий порядок:

1. `mcp__claude-context__search_code` (семантический поиск, основной путь)
2. `rg` (точечная верификация по найденным путям)
3. `rg --files` (только если нужно найти файл по имени)

Чек-лист для эффективного поиска:

1. Формулировать запрос как `компонент + действие + контекст` (например: `train.sh validate required env vars`, `prepare_binidx jsonl text key`, `infer_albatross auto clone`).
2. Первый проход делать с `limit: 6-10`.
3. Сразу задавать `extensionFilter` под задачу:
   - shell-оркестрация и раннеры: `.sh`
   - python-утилиты: `.py`
   - профили и модельные пресеты: `.env`
   - конфигурация tooling: `.toml`
   - спецификации/документация: `.md`
4. Приоритетно искать по директориям `scripts/`, `configs/`, `openspec/` и корневым `README.md`/`AGENTS.md`.
5. Если в топе много шума, переформулировать запрос через конкретные сущности (`RWKV_PEFT_DIR`, `RUN_NAME`, `ALBATROSS_MODEL`, `prepare_binidx.sh`).
6. После семантического поиска подтверждать факт в коде через `rg`/чтение файлов.
7. Проверять минимум 2-3 источника: скрипт + конфиг + спецификация/README.
8. Не считать checklist/status доказательством реализации без проверки исходников.
9. Не использовать `.beads/*` как источник истины по runtime-поведению без проверки исполняемых скриптов.

## Индексация (уменьшение шума)

При ручной переиндексации использовать `force=true`.
Игнор-паттерны для индексации задаются централизованно в `.codex/config.toml`.

Важно: для `claude-context` использовать один и тот же канонический абсолютный путь с завершающим `/`.

- Рекомендованный корень в этом репозитории: `/home/egor/code/rwkv-finetune/`
- Использовать этот путь одинаково во всех командах:
  - `mcp__claude-context__index_codebase`
  - `mcp__claude-context__get_indexing_status`
  - `mcp__claude-context__clear_index`
  - `mcp__claude-context__search_code`
- Не смешивать варианты с `/` и без `/`: инструмент может воспринимать их как разные индексные ключи.
- Если ранее смешанные варианты уже использовались, очистить индекс для обоих путей один раз и далее использовать только канонический путь.

## Локальная отладка (autonomous-feedback-loop)

Практические команды runtime-debugging собраны в `DEBUG.md`:
- inventory: `./debug/runtime-inventory.sh`
- probes: `./debug/probe.sh all`
- restart+probe: `./debug/restart-runtime.sh <runtime>`
- django eval: `./debug/eval-django.sh "<python code>"`
- frontend eval: `./debug/eval-frontend.sh "<js expression>"`

## Airflow orchestration (primary)

- Primary orchestration profile MUST быть `airflow`.
- Конфигурации с `ORCHESTRATION_PROFILE=mlops-lite` считаются невалидными для primary runtime.
- Поддерживаемый Python-диапазон для Airflow tooling: `3.9..3.12` (проверяется через preflight).
- Основные команды:
  - preflight: `./scripts/airflow_preflight.sh [--require-airflow]`
  - bootstrap: `./scripts/airflow_bootstrap.sh`
  - services: `./scripts/airflow_services.sh <start|stop|restart|status>`
  - trigger: `./scripts/run_pipeline.sh --conf-file <path>`
  - smoke: `./scripts/airflow_smoke.sh [--mode strict|fallback]`
- Для CI smoke MUST выполняться в strict-режиме.
- При сбоях и rollback использовать `docs/airflow-runbook.md` как основной operational guide.

## Стратегия датасетов и антидеградации модели

Базовая цель дообучения: повысить качество на задачах 1C:Enterprise программирования, не ухудшив общие способности модели.

### Обязательные принципы

- Использовать только adapter-first подход (`LoRA/QLoRA`): базовые веса считаются защищённым baseline.
- Не делать merge адаптера в базовую модель по умолчанию; merge допускается только отдельным явным решением.
- Для train/eval принимать только образцы, где пользовательский промпт на русском языке.
- Поддерживать два контура данных:
  - `core`: источники с явно допустимыми лицензиями.
  - `extended`: внутренний mixed-use контур с обязательным provenance.
- Любой образец без provenance (источник, лицензия, origin ref) не допускается в релиз.

### Баланс данных (стартовый baseline)

- генерация кода: `35%`
- рефакторинг: `35%`
- запросы 1C: `15%`
- объяснение/ревью: `15%`

Допуск по каждой категории: не более `5` процентных пунктов.
Генерация и рефакторинг должны оставаться паритетными в пределах допуска.

### Защита от catastrophic forgetting

- Применять replay/mix-in буфер общих данных (RU general + не-1C coding) как обязательную часть train.
- Стартовый диапазон replay-доли: `15-25%`, далее корректировать только по метрикам.
- Избегать агрессивного обучения: низкий learning rate, ранняя остановка, контроль overfitting на каждой итерации.
- Для малой VRAM (например, `16GB`) приоритет: разнообразие данных и ограничение эпох, а не форсирование числа шагов.

### Quality gates перед релизом датасета

- exact dedup и near dedup.
- проверка синтаксиса/диагностик BSL.
- фильтрация секретов и PII.
- контроль leakage между train/eval (репозиторно-временной split + near-dup контроль).

Если любой критический gate не пройден, релиз блокируется.

### Evaluation gates перед релизом адаптера

- Обязателен `domain eval` (1C coding) и `retention eval` (общие RU-задачи, логика, не-1C код).
- Релиз блокируется, если есть значимая регрессия по retention-метрикам относительно baseline.
- Рекомендуемый стартовый guardrail: не хуже `-3%` по агрегированной retention-оценке.

### Операционная политика

- Каждый релиз датасета должен быть versioned и сопровождаться manifest-артефактом.
- Результаты eval фиксировать по категориям задач и использовать для backlog hard-cases следующего релиза.
- При деградации качества откатываться к предыдущему адаптеру/датасету и пересобирать train-set, а не «докручивать» вслепую.

Связанный change для детализации требований: `openspec/changes/add-1c-dataset-strategy/`.
