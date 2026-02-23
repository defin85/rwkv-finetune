# Runbook: Airflow Orchestration

Этот документ описывает operational cycle для primary orchestration path (`airflow`) в репозитории `rwkv-finetune`.

## 1. Подготовка и запуск

1. Подготовить workspace-конфиг:

```bash
cd /home/egor/code/rwkv-finetune
cp configs/workspace.env.example configs/workspace.env
```

2. Проверить primary профиль:

```bash
grep -n '^ORCHESTRATION_PROFILE=' configs/workspace.env
```

Ожидаемое значение: `ORCHESTRATION_PROFILE=airflow`.

3. Установить зависимости:

```bash
./scripts/bootstrap.sh
./scripts/airflow_bootstrap.sh
```

4. Поднять сервисы:

```bash
./scripts/airflow_services.sh start
./scripts/airflow_services.sh status
```

5. Проверить smoke:

```bash
./scripts/airflow_smoke.sh
```

## 2. Штатный запуск pipeline

1. Подготовить `conf` для DAG:

```json
{
  "input_jsonl": "/home/egor/code/rwkv-finetune/data/raw/sample.jsonl",
  "output_prefix": "/home/egor/code/rwkv-finetune/data/processed/sample",
  "data_prefix": "/home/egor/code/rwkv-finetune/data/processed/sample_text_document",
  "load_model": "/home/egor/code/rwkv-finetune/models/base/YOUR_MODEL.pth",
  "run_name": "rwkv-airflow-manual-001"
}
```

2. Триггернуть DAG:

```bash
./scripts/run_pipeline.sh \
  --run-id rwkv-airflow-manual-001 \
  --conf-file /path/to/conf.json
```

3. Проверить статус run:

```bash
airflow dags list-runs -d rwkv_train_lifecycle
airflow tasks states-for-dag-run rwkv_train_lifecycle rwkv-airflow-manual-001
```

## 3. Восстановление после fail

1. Проверить сервисы и перезапустить при необходимости:

```bash
./scripts/airflow_services.sh status
./scripts/airflow_services.sh restart
```

2. Проверить audit trail:

```bash
ls -la orchestration/airflow/runtime/audit/
```

Audit по задачам хранится в `orchestration/airflow/runtime/audit/<dag_run_id>/`.

3. Проверить gate-артефакты run:

```bash
ls -la runs/<run_name>/gates/
cat runs/<run_name>/gates/dataset_quality_gate.json
cat runs/<run_name>/gates/eval_gate.json
```

4. Проверить release/eval:

```bash
cat runs/<run_name>/eval_summary.json
cat runs/<run_name>/release_manifest.json
```

5. После исправления причины fail запускать новый run с новым `run_name`/`run_id`.

## 4. Rollback к предыдущему стабильному адаптеру

Поскольку release в текущем контуре manifest-first, откат выполняется выбором предыдущего `release_manifest.json` со статусом `released`.

1. Найти стабильные release manifests:

```bash
python - <<'PY'
import glob
import json
from pathlib import Path

rows = []
for path in glob.glob("runs/*/release_manifest.json"):
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    if str(data.get("status", "")).lower() == "released":
        rows.append((data.get("created_at", ""), data.get("run_name", p.parent.name), path))

for created_at, run_name, path in sorted(rows, reverse=True):
    print(f"{created_at}\t{run_name}\t{path}")
PY
```

2. Выбрать целевой предыдущий стабильный run (не последний проблемный).

3. Обновить deploy-конфиг потребителя на выбранный manifest path:

```bash
export RWKV_RELEASE_MANIFEST=/home/egor/code/rwkv-finetune/runs/<stable_run>/release_manifest.json
```

4. Перезапустить consumer/inference сервис, который читает release manifest.

## 5. Known limitation (на дату 2026-02-23)

- На окружении `Airflow 3.0.6 + Python 3.14.3` команда `airflow dags test` падает в execution API (`cadwyn` typing error).
- `./scripts/airflow_smoke.sh` покрывает это через wrapper fallback и всё равно валидирует expected outputs.
