# RWKV Finetune Workspace for 1C:Enterprise (WSL, no Docker)

This repository provides a local RWKV v7 finetuning workspace on Windows + WSL.
Primary orchestration path is Apache Airflow (`ORCHESTRATION_PROFILE=airflow`).
The goal is finetuning for 1C:Enterprise programming tasks while preserving general coding quality.

## What is included

- Reproducible workspace layout for data, models, logs, and runs
- Bootstrap scripts for Python environment and training dependencies
- Airflow orchestration scripts (`bootstrap`, `services`, `trigger`, `smoke`)
- Airflow DAG `rwkv_train_lifecycle`:
  - `prepare_dataset`
  - `check_dataset_quality`
  - `train_adapter`
  - `evaluate_adapter`
  - `check_eval_gates`
  - `release_adapter`
- Training wrappers:
  - LoRA BF16
  - QLoRA NF4
  - QLoRA INT8

## Folder layout

```text
rwkv-finetune/
  configs/
    model/
    profile/
    workspace.env.example
  data/
    raw/
    processed/
  models/
    base/
    adapters/
    merged/
  orchestration/
    airflow/
      dags/
      plugins/
      runtime/
  scripts/
  third_party/
  runs/
  logs/
```

## Requirements

- Windows 11 + WSL2
- NVIDIA Windows driver with WSL CUDA support
- WSL distro with `python3`, `python3-venv`, `git`
- GPU available inside WSL (`nvidia-smi`)

Important: do not install Linux NVIDIA display driver inside WSL.

## Quick Start (Airflow Primary Path)

1. Configure workspace variables:

```bash
cd /home/egor/code/rwkv-finetune
cp configs/workspace.env.example configs/workspace.env
```

2. Bootstrap training dependencies:

```bash
./scripts/bootstrap.sh
```

3. Bootstrap Airflow runtime:

```bash
./scripts/airflow_bootstrap.sh
```

4. Start Airflow services:

```bash
./scripts/airflow_services.sh start
```

5. Run DAG smoke:

```bash
./scripts/airflow_smoke.sh
```

6. Trigger pipeline:

```bash
cat > /tmp/rwkv-airflow-conf.json <<'EOF'
{
  "input_jsonl": "/home/egor/code/rwkv-finetune/data/raw/sample.jsonl",
  "output_prefix": "/home/egor/code/rwkv-finetune/data/processed/sample",
  "data_prefix": "/home/egor/code/rwkv-finetune/data/processed/sample_text_document",
  "load_model": "/home/egor/code/rwkv-finetune/models/base/YOUR_MODEL.pth",
  "run_name": "rwkv-airflow-manual-001"
}
EOF

./scripts/run_pipeline.sh \
  --run-id rwkv-airflow-manual-001 \
  --conf-file /tmp/rwkv-airflow-conf.json
```

7. Check runs and tasks:

```bash
airflow dags list-runs -d rwkv_train_lifecycle
airflow tasks states-for-dag-run rwkv_train_lifecycle rwkv-airflow-manual-001
```

## Airflow Policy

- `ORCHESTRATION_PROFILE` MUST be `airflow` for production execution.
- `mlops-lite` is archived and is not a valid primary profile.
- GPU-bound tasks are serialized via Airflow pool (`rwkv_gpu_pool`, slots=`1`).
- Release is blocked when dataset quality gate or eval gates are `FAIL`.

## Legacy Wrapper Execution (Debug Only)

Direct wrapper execution remains available for local debugging:

```bash
./scripts/prepare_binidx.sh data/raw/sample.jsonl data/processed/sample
./scripts/train_lora.sh \
  --load-model /home/egor/code/rwkv-finetune/models/base/YOUR_MODEL.pth \
  --data-prefix /home/egor/code/rwkv-finetune/data/processed/sample_text_document \
  --run-name rwkv7-lora-test
```

## Model configs

Available model presets:

- `configs/model/rwkv7-0.4b.env`
- `configs/model/rwkv7-1.5b.env`
- `configs/model/rwkv7-3b.env`

Default wrappers use `rwkv7-1.5b`.

## Runbook

Operational procedures:

- `docs/airflow-runbook.md`

## Albatross inference

For local RWKV inference via `BlinkDL/Albatross`:

```bash
python scripts/infer_albatross.py \
  --model /home/egor/code/rwkv-finetune/models/base/rwkv7-g1-1.5b-20250429-ctx4096.pth \
  --prompt "User: explain recursion in Python. Assistant:" \
  --tokens 128 \
  --batch 1 \
  --auto-clone
```

Shortcut wrapper:

```bash
ALBATROSS_MODEL=/home/egor/code/rwkv-finetune/models/base/rwkv7-g1-1.5b-20250429-ctx4096.pth \
./scripts/run_albatross.sh --auto-clone --tokens 128
```
