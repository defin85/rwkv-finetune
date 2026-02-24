#!/usr/bin/env python3
"""Build deterministic identity hotfix datasets with replay mix."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate identity-hotfix dataset in canonical chat format "
            "'User: ...\\nAssistant: ...' with replay samples."
        )
    )
    parser.add_argument(
        "--train-output",
        default="data/raw/identity_hotfix_v4.jsonl",
        help="Output path for train JSONL.",
    )
    parser.add_argument(
        "--eval-output",
        default="data/raw/identity_hotfix_v4_eval.jsonl",
        help="Output path for eval JSONL.",
    )
    parser.add_argument(
        "--manifest-output",
        default="data/raw/identity_hotfix_v4.manifest.json",
        help="Output path for dataset manifest JSON.",
    )
    parser.add_argument(
        "--dataset-name",
        default="identity_hotfix_v4",
        help="Dataset name written to manifest metadata.",
    )
    parser.add_argument(
        "--train-size",
        type=int,
        default=960,
        help="Number of rows in train split.",
    )
    parser.add_argument(
        "--eval-size",
        type=int,
        default=192,
        help="Number of rows in eval split.",
    )
    parser.add_argument(
        "--identity-ratio",
        type=float,
        default=0.42,
        help="Fraction of identity rows in both train/eval splits.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260225,
        help="Deterministic shuffle seed.",
    )
    return parser.parse_args()


def format_row(user_prompt: str, assistant_reply: str) -> str:
    user = " ".join(user_prompt.strip().split())
    assistant = " ".join(assistant_reply.strip().split())
    return f"User: {user}\nAssistant: {assistant}"


def dedup_keep_order(rows: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for row in rows:
        if row in seen:
            continue
        seen.add(row)
        result.append(row)
    return result


def build_identity_candidates() -> list[str]:
    core_identity_prompts = [
        "кто ты?",
        "представься кратко.",
        "как называется твоя модель?",
        "какая модель отвечает в этом чате?",
        "скажи имя своей модели.",
        "уточни модель одним предложением.",
        "какая у тебя базовая модель?",
        "какой у тебя идентификатор модели?",
        "назови модель без дополнительных пояснений.",
        "что за модель сейчас отвечает?",
        "можешь назвать свою модель?",
        "как тебя корректно идентифицировать?",
        "напомни, какая ты модель.",
        "кто сейчас генерирует ответ?",
        "какая модель активна?",
        "ты из семейства RWKV?",
        "назови текущую модель в одном ответе.",
        "подтверди модель, которая даёт ответ.",
        "модель в этом диалоге — какая?",
        "назови модель и только модель.",
        "что за модель используется сейчас?",
        "кратко укажи имя модели.",
        "какую модель указать в карточке?",
        "какое корректное имя модели?",
        "какой model name у тебя?",
        "как тебя подписать в UI?",
        "как указывать тебя в документации?",
        "кто ты как LLM?",
        "ты какая LLM-модель?",
        "назови model id.",
        "сформулируй identity модели.",
        "дай корректную идентификацию модели.",
        "подтверди название модели для запуска.",
        "что писать в поле model при отчёте?",
        "какая модель используется по факту?",
        "кто ты в контексте этого окружения?",
        "какую модель ты представляешь?",
        "какая модель отвечает на этот запрос?",
        "что у тебя за model family?",
        "подтверди, что за модель здесь работает.",
        "что за модель на этом endpoint?",
        "какой model label у тебя сейчас?",
        "какую модель видит пользователь?",
        "какое имя модели должно быть в логе?",
        "напиши модель для карточки эксперимента.",
        "какое название модели в этом чате?",
        "скажи своё имя как модели ассистента.",
    ]
    misidentification_prompts = [
        "ты qwen?",
        "ты модель qwen?",
        "это qwen или rwkv?",
        "могу записать, что ты qwen?",
        "правильно ли, что ты qwen?",
        "ты chatgpt?",
        "это chatgpt или rwkv?",
        "вы openai модель?",
        "правильно, что ты openai assistant?",
        "это gpt модель?",
        "можно считать, что здесь gpt-4?",
        "можно подписать тебя как chatgpt?",
        "модель от openai сейчас отвечает?",
        "ты работаешь как gpt?",
        "для отчёта писать openai или rwkv?",
        "я правильно понял, что это chatgpt?",
        "в этом чате модель qwen или rwkv?",
        "это endpoint с chatgpt?",
        "могу в лог записать openai?",
        "скажи, это qwen, chatgpt или rwkv?",
    ]
    temporal_prompts = [
        "когда была обучена текущая модель?",
        "в каком году обучена эта модель?",
        "для этой модели какой сейчас год без внешних источников?",
        "сколько лет этой модели?",
        "какая дата обучения у этой модели?",
        "для модели какой knowledge cutoff?",
        "у этой модели есть доступ к текущей дате?",
        "можешь назвать текущий год для этой модели?",
        "какой год обучения у модели в этом чате?",
        "какая версия знаний по времени у этой модели?",
        "модель знает, какой сейчас месяц и год?",
        "модель может проверить текущую дату?",
        "когда выпущена модель, которая сейчас отвечает?",
        "какой временной период знаний у этой модели?",
        "какой training date у текущей модели?",
    ]
    prompt_styles = [
        "{prompt}",
        "ответь одной строкой: {prompt}",
        "кратко: {prompt}",
        "без лишних слов: {prompt}",
        "формат ответа: одно предложение. {prompt}",
        "нужен ответ для лога, лаконично: {prompt}",
    ]
    identity_answers = [
        "В этом чате используется модель RWKV-7.",
        "Текущая модель в рантайме: RWKV-7.",
        "Здесь отвечает языковая модель RWKV-7.",
        "Идентификатор модели в этом окружении: RWKV-7.",
        "Model name в этом запуске: RWKV-7.",
        "Для протокола укажи модель RWKV-7.",
        "В данном endpoint активна модель RWKV-7.",
        "В этом диалоге работает RWKV-7.",
        "Здесь используется модель семейства RWKV-7.",
        "Текущий движок модели: RWKV-7.",
        "В этом окружении активна модель RWKV-7.",
        "Корректная идентификация модели: RWKV-7.",
    ]
    temporal_answers = [
        "В этом чате отвечает модель RWKV-7; точная дата обучения зависит от выбранного checkpoint.",
        "Я модель RWKV-7, и без внешнего источника не определяю текущий календарный год.",
        "Текущая модель здесь RWKV-7; актуальную дату нужно брать из системного времени окружения.",
        "В этом запуске используется RWKV-7; по времени я опираюсь на доступные данные окружения.",
        "Я RWKV-7, а точный период обучения определяется конкретным загруженным checkpoint.",
        "Здесь активна модель RWKV-7; текущую дату следует проверять внешним инструментом.",
    ]

    rows: list[str] = []
    all_prompts = core_identity_prompts + misidentification_prompts + temporal_prompts
    for base_index, prompt in enumerate(all_prompts):
        lower_prompt = prompt.lower()
        is_temporal = any(token in lower_prompt for token in ("год", "дата", "обуч", "время", "cutoff"))
        answers = temporal_answers if is_temporal else identity_answers
        for style_index, style in enumerate(prompt_styles):
            user = style.format(prompt=prompt)
            answer = answers[(base_index + style_index) % len(answers)]
            rows.append(format_row(user, answer))
    return dedup_keep_order(rows)


def build_replay_candidates() -> list[str]:
    replay_rows: list[str] = []

    python_actions = [
        ("отфильтровать", "сначала опиши условие фильтра и добавь проверку краевых случаев"),
        ("отсортировать", "используй key-функцию и явно зафиксируй направление сортировки"),
        ("сгруппировать", "собери структуру групп по ключу и проверь пустой вход"),
        ("объединить", "нормализуй типы данных перед объединением"),
        ("дедуплицировать", "зафиксируй правило уникальности и порядок элементов"),
        ("разбить на батчи", "держи размер батча параметром и обработай хвост"),
        ("преобразовать", "выдели преобразование в отдельную функцию"),
        ("валидацировать", "верни список ошибок, а не одно булево значение"),
        ("агрегировать", "используй явные начальные значения аккумуляторов"),
        ("логировать", "пиши структурированные поля вместо длинной строки"),
    ]
    python_objects = [
        ("список словарей", "проверь существование ключей до доступа"),
        ("список строк", "учти регистр и пробелы по краям"),
        ("словарь с вложенными полями", "используй безопасный доступ через get"),
        ("таблицу CSV", "фиксируй кодировку и разделитель"),
        ("JSON-файл", "отдельно валидируй схему и содержимое"),
        ("набор дат", "приводи всё к одному timezone"),
        ("список заказов", "отдели этап очистки от бизнес-логики"),
    ]
    python_prompt_variants = [
        "как в Python {action} {obj}?",
        "дай пошаговый план: {action} {obj} в Python.",
        "какая практичная схема для задачи: {action} {obj}?",
    ]
    for action, action_tip in python_actions:
        for obj, object_tip in python_objects:
            for prompt_tmpl in python_prompt_variants:
                replay_rows.append(
                    format_row(
                        prompt_tmpl.format(action=action, obj=obj),
                        (
                            f"Для задачи '{action} {obj}' начни с маленького воспроизводимого примера, "
                            f"затем {action_tip}. Для входа '{obj}' {object_tip}."
                        ),
                    )
                )

    onec_actions = [
        ("прочитать", "используй типизированные проверки до обращения к полям"),
        ("обновить", "оборачивай изменения в явную транзакцию при пакетной записи"),
        ("провести", "сначала валидируй входные данные документа"),
        ("сформировать", "вынеси вычисления в отдельный общий модуль"),
        ("проверить", "возвращай диагностические сообщения, а не только булево значение"),
        ("записать", "контролируй права и режим блокировки"),
        ("рассчитать", "фиксируй правила округления на уровне функции"),
        ("подготовить", "держи подготовку данных отдельно от вывода"),
        ("оптимизировать", "замеряй время до и после изменения запроса"),
    ]
    onec_objects = [
        ("документ реализации", "проверь заполнение реквизитов перед проведением"),
        ("справочник контрагентов", "нормализуй ИНН/КПП и ключ поиска"),
        ("регистр накопления", "используй минимальный набор измерений в отборе"),
        ("табличную часть", "обрабатывай пустые строки и дубли"),
        ("запрос к базе", "оставь только нужные поля в выборке"),
        ("обработку обмена", "добавь идемпотентный ключ операции"),
        ("печатную форму", "раздели данные и шаблон вывода"),
    ]
    onec_prompt_variants = [
        "как в 1С {action} {obj} без регрессий?",
        "дай практический алгоритм: {action} {obj} в 1С.",
        "что важно проверить перед тем как {action} {obj}?",
    ]
    for action, action_tip in onec_actions:
        for obj, object_tip in onec_objects:
            for prompt_tmpl in onec_prompt_variants:
                replay_rows.append(
                    format_row(
                        prompt_tmpl.format(action=action, obj=obj),
                        (
                            f"В задаче '{action} {obj}' зафиксируй предусловия, затем {action_tip}. "
                            f"Для '{obj}' {object_tip}."
                        ),
                    )
                )

    sql_actions = [
        ("отфильтровать строки", "используй индексируемые поля в предикате"),
        ("посчитать агрегаты", "добавляй GROUP BY только по реально нужным колонкам"),
        ("обновить записи", "сначала проверь выборку через SELECT"),
        ("объединить таблицы", "согласуй типы ключей до JOIN"),
        ("найти дубликаты", "фиксируй критерий дубля в одном выражении"),
        ("построить отчёт", "выноси тяжёлые вычисления в CTE"),
        ("ускорить запрос", "сравни план выполнения до и после изменений"),
    ]
    sql_objects = [
        ("по заказам", "ограничи период и статус в условиях"),
        ("по платежам", "учти отменённые операции отдельно"),
        ("по остаткам", "проверяй источники с разной частотой обновления"),
        ("по пользователям", "избегай SELECT * в продовых отчётах"),
        ("по логам", "разделяй хранение и отчётные выборки"),
        ("по интеграции", "обрабатывай пропуски внешних идентификаторов"),
    ]
    sql_prompt_variants = [
        "как в SQL {action} {obj}?",
        "дай безопасный шаблон: {action} {obj}.",
        "какой рабочий порядок для задачи '{action} {obj}'?",
    ]
    for action, action_tip in sql_actions:
        for obj, object_tip in sql_objects:
            for prompt_tmpl in sql_prompt_variants:
                replay_rows.append(
                    format_row(
                        prompt_tmpl.format(action=action, obj=obj),
                        (
                            f"Для SQL-задачи '{action} {obj}' сначала зафиксируй входные ограничения, "
                            f"затем {action_tip}. Для контекста '{obj}' {object_tip}."
                        ),
                    )
                )

    devops_actions = [
        ("собрать логи сервиса", "начни с фильтрации по времени и уровню ошибки"),
        ("перезапустить процесс", "проверь health-check сразу после рестарта"),
        ("проверить сеть", "измерь доступность hop-by-hop, а не только конечный адрес"),
        ("настроить systemd unit", "задай Restart policy и лимиты ресурсов"),
        ("диагностировать память", "сними baseline перед нагрузкой"),
        ("стабилизировать деплой", "добавь проверку готовности перед переключением трафика"),
    ]
    devops_objects = [
        ("в WSL", "учти различие путей Windows и Linux"),
        ("в Airflow", "проверь scheduler и webserver отдельно"),
        ("на GPU-ноде", "контролируй занятость VRAM перед запуском"),
        ("в CI-job", "сохрани артефакты диагностики в шаге fail"),
        ("в Python-сервисе", "включи структурированный лог с request-id"),
        ("в batch-задаче", "добавь идемпотентность по run-id"),
    ]
    devops_prompt_variants = [
        "какой практичный план, чтобы {action} {obj}?",
        "что делать шаг за шагом: {action} {obj}?",
        "дай checklist для задачи: {action} {obj}.",
    ]
    for action, action_tip in devops_actions:
        for obj, object_tip in devops_objects:
            for prompt_tmpl in devops_prompt_variants:
                replay_rows.append(
                    format_row(
                        prompt_tmpl.format(action=action, obj=obj),
                        (
                            f"Для задачи '{action} {obj}' сначала зафиксируй текущее состояние, "
                            f"потом {action_tip}. В контексте '{obj}' {object_tip}."
                        ),
                    )
                )

    testing_actions = [
        ("написать unit-тест", "проверь happy-path и один edge-case"),
        ("покрыть регрессию", "добавь тест именно на ранее упавший сценарий"),
        ("подготовить мок", "мокай внешний I/O, а не бизнес-логику"),
        ("разделить тесты", "отдели быстрые unit от медленных интеграционных"),
        ("проверить контракт", "зафиксируй вход/выход через schema assertions"),
        ("собрать smoke", "оставь только критические сценарии запуска"),
    ]
    testing_objects = [
        ("для Python-функции", "используй параметризацию для похожих кейсов"),
        ("для Airflow DAG", "проверяй и success-path, и блокировку downstream"),
        ("для REST-эндпоинта", "контролируй коды ответа и структуру JSON"),
        ("для SQL-запроса", "фиксируй тестовый датасет с предсказуемым результатом"),
        ("для 1С-обработки", "изолируй side effects в отдельном слое"),
        ("для CLI-утилиты", "проверь коды выхода и текст ошибок"),
    ]
    testing_prompt_variants = [
        "как лучше {action} {obj}?",
        "дай рабочий шаблон, чтобы {action} {obj}.",
        "на что смотреть в первую очередь: {action} {obj}?",
    ]
    for action, action_tip in testing_actions:
        for obj, object_tip in testing_objects:
            for prompt_tmpl in testing_prompt_variants:
                replay_rows.append(
                    format_row(
                        prompt_tmpl.format(action=action, obj=obj),
                        (
                            f"Когда нужно '{action} {obj}', начни с чёткого критерия успеха, "
                            f"затем {action_tip}. Для случая '{obj}' {object_tip}."
                        ),
                    )
                )

    return dedup_keep_order(replay_rows)


def sample_without_overlap(
    rows: list[str], train_count: int, eval_count: int, rng: random.Random
) -> tuple[list[str], list[str]]:
    if train_count < 0 or eval_count < 0:
        raise ValueError("Split sizes must be non-negative")
    if train_count + eval_count > len(rows):
        raise ValueError(
            f"Not enough candidates: requested={train_count + eval_count}, available={len(rows)}"
        )
    pool = list(rows)
    rng.shuffle(pool)
    train_rows = pool[:train_count]
    eval_rows = pool[train_count : train_count + eval_count]
    return train_rows, eval_rows


def write_jsonl(path: Path, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps({"text": row}, ensure_ascii=False) + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    args = parse_args()
    if args.train_size < 1:
        raise ValueError("--train-size must be >= 1")
    if args.eval_size < 1:
        raise ValueError("--eval-size must be >= 1")
    if not 0.1 <= args.identity_ratio <= 0.9:
        raise ValueError("--identity-ratio must be in [0.1, 0.9]")

    rng = random.Random(args.seed)

    identity_candidates = build_identity_candidates()
    replay_candidates = build_replay_candidates()

    train_identity = round(args.train_size * args.identity_ratio)
    eval_identity = round(args.eval_size * args.identity_ratio)
    train_replay = args.train_size - train_identity
    eval_replay = args.eval_size - eval_identity

    train_id_rows, eval_id_rows = sample_without_overlap(
        identity_candidates, train_identity, eval_identity, rng
    )
    train_replay_rows, eval_replay_rows = sample_without_overlap(
        replay_candidates, train_replay, eval_replay, rng
    )

    train_rows = train_id_rows + train_replay_rows
    eval_rows = eval_id_rows + eval_replay_rows
    rng.shuffle(train_rows)
    rng.shuffle(eval_rows)

    train_path = Path(args.train_output).resolve()
    eval_path = Path(args.eval_output).resolve()
    manifest_path = Path(args.manifest_output).resolve()

    write_jsonl(train_path, train_rows)
    write_jsonl(eval_path, eval_rows)

    manifest = {
        "dataset_name": args.dataset_name,
        "created_by": "scripts/build_identity_hotfix_dataset.py",
        "seed": args.seed,
        "train": {
            "path": str(train_path),
            "rows_total": len(train_rows),
            "rows_identity": len(train_id_rows),
            "rows_replay": len(train_replay_rows),
            "sha256": sha256_file(train_path),
        },
        "eval": {
            "path": str(eval_path),
            "rows_total": len(eval_rows),
            "rows_identity": len(eval_id_rows),
            "rows_replay": len(eval_replay_rows),
            "sha256": sha256_file(eval_path),
        },
        "candidate_inventory": {
            "identity_candidates": len(identity_candidates),
            "replay_candidates": len(replay_candidates),
        },
    }

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"train rows: {len(train_rows)} -> {train_path}")
    print(f"eval rows: {len(eval_rows)} -> {eval_path}")
    print(f"manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
