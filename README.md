# RWKV Finetune Workspace for 1C:Enterprise (WSL, no Docker)

This repository provides a local RWKV v7 finetuning workspace on Windows + WSL.
Primary orchestration path is Apache Airflow (`ORCHESTRATION_PROFILE=airflow`).
The goal is finetuning for 1C:Enterprise programming tasks while preserving general coding quality.

## What is included

- Reproducible workspace layout for data, models, logs, and runs
- Bootstrap scripts for Python environment and training dependencies
- Airflow orchestration scripts (`preflight`, `bootstrap`, `services`, `trigger`, `smoke`)
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
- Dataset builder for `1C-Expert-v4` release profile (plain text + release gates)

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

2. Run Airflow preflight (Python/Airflow compatibility):

```bash
./scripts/airflow_preflight.sh
```

3. Bootstrap training dependencies:

```bash
./scripts/bootstrap.sh
```

4. Bootstrap Airflow runtime:

```bash
./scripts/airflow_bootstrap.sh
```

5. Start Airflow services:

```bash
./scripts/airflow_services.sh start
```

6. Run DAG smoke:

```bash
./scripts/airflow_smoke.sh --mode fallback
```

7. Trigger pipeline:

```bash
cat > /tmp/rwkv-airflow-conf.json <<'EOF'
{
  "input_jsonl": "/home/egor/code/rwkv-finetune/data/raw/sample.jsonl",
  "output_prefix": "/home/egor/code/rwkv-finetune/data/processed/sample",
  "data_prefix": "/home/egor/code/rwkv-finetune/data/processed/sample_text_document",
  "load_model": "/home/egor/code/rwkv-finetune/models/base/rwkv7-g1-0.4b-20250324-ctx4096.pth",
  "run_name": "rwkv-airflow-manual-001"
}
EOF

./scripts/run_pipeline.sh \
  --run-id rwkv-airflow-manual-001 \
  --conf-file /tmp/rwkv-airflow-conf.json
```

8. Check runs and tasks:

```bash
airflow dags list-runs -d rwkv_train_lifecycle
airflow tasks states-for-dag-run rwkv_train_lifecycle rwkv-airflow-manual-001
```

## Airflow Policy

- `ORCHESTRATION_PROFILE` MUST be `airflow` for production execution.
- `mlops-lite` is archived and is not a valid primary profile.
- Supported Python range for Airflow scripts is `3.9..3.12`.
- GPU-bound tasks are serialized via Airflow pool (`rwkv_gpu_pool`, slots=`1`).
- Release is blocked when dataset quality gate or eval gates are `FAIL`.
- CI policy: smoke uses `./scripts/airflow_smoke.sh --mode strict`.
- Admin bootstrap is disabled by default (`AIRFLOW_CREATE_ADMIN=0`); enable only with a strong unique password.

## Legacy Wrapper Execution (Debug Only)

Direct wrapper execution remains available for local debugging:

```bash
./scripts/prepare_binidx.sh data/raw/sample.jsonl data/processed/sample
./scripts/train.sh \
  --load-model /home/egor/code/rwkv-finetune/models/base/rwkv7-g1-0.4b-20250324-ctx4096.pth \
  --data-prefix /home/egor/code/rwkv-finetune/data/processed/sample_text_document \
  --run-name rwkv7-lora-test
```

`train.sh` accepts explicit `--model/--profile` or defaults from:

- `TRAIN_MODEL_CONFIG` (default `configs/model/rwkv7-0.4b.env`)
- `TRAIN_PROFILE_CONFIG` (default `configs/profile/lora-bf16.env`)

## Model configs

Available model presets:

- `configs/model/rwkv7-0.4b.env`
- `configs/model/rwkv7-1.5b.env`
- `configs/model/rwkv7-3b.env`

Default wrappers use `rwkv7-0.4b`.

## Runbook

Operational procedures:

- `docs/airflow-runbook.md`

## Identity Hotfix v4 (Recommended)

`identity_hotfix_v4` is the default identity fine-tune dataset with replay mix, stronger identity coverage, and stricter leakage quality gates.

1. Build train/eval splits and manifest:

```bash
python scripts/build_identity_hotfix_dataset.py \
  --train-output data/raw/identity_hotfix_v4.jsonl \
  --eval-output data/raw/identity_hotfix_v4_eval.jsonl \
  --manifest-output data/raw/identity_hotfix_v4.manifest.json \
  --dataset-name identity_hotfix_v4
```

2. Validate quality gates:

```bash
python scripts/check_dataset_quality.py \
  --input data/raw/identity_hotfix_v4.jsonl \
  --output data/raw/identity_hotfix_v4.manifest.json \
  --strict
```

3. Trigger Airflow pipeline with v4 config:

```bash
./scripts/run_pipeline.sh \
  --run-id identity-hotfix-v4-001 \
  --conf-file /home/egor/code/rwkv-finetune/configs/airflow/identity_hotfix_v4.conf.json
```

If DAG is triggered from UI without custom `Config`, defaults are read from `configs/workspace.env` via:
`RWKV_AIRFLOW_INPUT_JSONL`, `RWKV_AIRFLOW_DATASET_MANIFEST`, `RWKV_AIRFLOW_TRAIN_WRAPPER`.

## 1C-Expert-v4 Dataset Pipeline

Dataset lifecycle policy:

- `configs/dataset/dataset-lifecycle.policy.json`

Canonical sample contract for lifecycle validation:

```json
{
  "user_prompt": "<русский prompt>",
  "assistant_response": "<answer>",
  "metadata": {
    "source": "<source-id>",
    "license": "<license>",
    "origin_ref": "<origin-ref>",
    "contour": "core|extended",
    "segment": "<segment>",
    "split": "train|dev|eval"
  },
  "text": "User: <prompt>\\nAssistant: <answer>"
}
```

Release validator for canonical splits:

```bash
python scripts/validate_dataset_release.py \
  --train /path/to/train.jsonl \
  --eval /path/to/eval.jsonl \
  --manifest-output data/curated/example.manifest.json \
  --dataset-name example \
  --dataset-version v0
```

Machine-readable profile:

- `configs/dataset/1c-expert-v4.profile.json`

Builder command (produces plain text `Instruction/Response + <|endoftext|>` and release report):

```bash
python scripts/build_1c_expert_v4_dataset.py \
  --profile configs/dataset/1c-expert-v4.profile.json \
  --bsl-root /path/to/onec/configuration \
  --coding-jsonl /path/to/coding.jsonl \
  --ru-jsonl /path/to/ru_identity.jsonl \
  --output-text data/raw/1c_expert_v4_train.txt \
  --report-output data/raw/1c_expert_v4.release.report.json
```

Output report includes:

- module coverage (`common/manager/object`)
- mix counters (`onec_bsl/coding_general/ru_identity`)
- format gates (raw JSON object detection, `<|endoftext|>`, `Instruction/Response`)
- hard minimum size gate (default from profile: `200 MB`)

Smoke command (build + `prepare_binidx.sh` + artifact check):

```bash
./scripts/smoke_1c_expert_v4.sh
```

Expected binidx data prefix from smoke:

- `<tmp>/processed/smoke_text_document`

## Trusted Repo-Family Builder

Для локального trusted-корпуса из нескольких sibling 1C-репозиториев используйте отдельный builder:

```bash
python scripts/build_repo_family_trusted_corpus.py \
  --family-manifest /path/to/repo-family.manifest.json \
  --train-output data/raw/repo_family_train.jsonl \
  --dev-output data/raw/repo_family_dev.jsonl \
  --eval-output data/raw/repo_family_eval.jsonl \
  --report-output data/raw/repo_family.release.report.json \
  --hard-min-mb 200
```

Минимальный `repo_family_manifest`:

```json
{
  "source_family_id": "rolf-family",
  "repo_roots": [
    "/abs/path/to/DO_Rolf",
    "/abs/path/to/GetDocflowEvents"
  ],
  "canonical_snapshot_root": "/abs/path/to/DO_Rolf",
  "training_permission": true,
  "usage_policy": "internal-training",
  "license": "internal",
  "origin_ref": "local://rolf-family"
}
```

Builder:

- рассматривает sibling-репозитории как один `source family`;
- канонизирует snapshot по `canonical_snapshot_root`;
- исключает `.epf`-связанные BSL-модули из trusted `v1`;
- строит `history_method_change` только из локализуемых git-коммитов;
- формирует `core/onec_bsl` sample с русским `user_prompt`;
- выносит поздние history changes в `dev/eval` и удаляет exact/near duplicates из train;
- блокирует релиз, если `attained_unique_volume_mb < hard_min_mb`.

## Albatross inference

For local RWKV inference via `BlinkDL/Albatross`:

```bash
python scripts/infer_albatross.py \
  --model /home/egor/code/rwkv-finetune/models/base/rwkv7-g1-0.4b-20250324-ctx4096.pth \
  --prompt "User: explain recursion in Python. Assistant:" \
  --tokens 128 \
  --batch 1 \
  --auto-clone
```

Shortcut wrapper:

```bash
ALBATROSS_MODEL=/home/egor/code/rwkv-finetune/models/base/rwkv7-g1-0.4b-20250324-ctx4096.pth \
./scripts/run_albatross.sh --auto-clone --tokens 128
```
