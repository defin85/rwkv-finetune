# RWKV Finetune Workspace for 1C:Enterprise (WSL, no Docker)

This folder is a ready-to-run workspace for RWKV v7 LoRA/QLoRA finetuning with `RWKV-PEFT` on Windows + WSL.
The primary goal is to finetune models for 1C:Enterprise development tasks with a programming-first focus.

## What is included

- Reproducible folder layout for data, base models, adapters, logs, and runs
- Bootstrap script to install Python environment and training dependencies
- Healthcheck script for GPU / CUDA / PyTorch / DeepSpeed / bitsandbytes
- Data conversion script: `jsonl -> binidx` for RWKV training
- Workflow oriented toward 1C:Enterprise programming datasets and coding prompts
- Training wrappers for:
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
  scripts/
  third_party/
  runs/
  logs/
```

## Requirements

- Windows 11 + WSL2
- NVIDIA Windows driver with WSL CUDA support
- WSL distro with `python3`, `python3-venv`, `git`
- GPU available inside WSL (`nvidia-smi` should work)

Important: do not install Linux NVIDIA display driver inside WSL.

## Quick start

1. Configure workspace variables:

```bash
cd /home/egor/code/rwkv-finetune
cp configs/workspace.env.example configs/workspace.env
```

2. Bootstrap dependencies:

```bash
./scripts/bootstrap.sh
```

3. Run health check:

```bash
./scripts/healthcheck.sh
```

4. Put RWKV base checkpoint `.pth` into `models/base/`.

5. Prepare training data (JSONL with key `text`) and convert to binidx:

```bash
./scripts/prepare_binidx.sh data/raw/sample.jsonl data/processed/sample
```

This creates:

- `data/processed/sample_text_document.bin`
- `data/processed/sample_text_document.idx`

Use `data/processed/sample_text_document` as `--data-prefix` for training.

6. Start training:

```bash
./scripts/train_lora.sh \
  --load-model /home/egor/code/rwkv-finetune/models/base/YOUR_MODEL.pth \
  --data-prefix /home/egor/code/rwkv-finetune/data/processed/sample_text_document \
  --run-name rwkv7-lora-test
```

Or QLoRA:

```bash
./scripts/train_qlora_nf4.sh \
  --load-model /home/egor/code/rwkv-finetune/models/base/YOUR_MODEL.pth \
  --data-prefix /home/egor/code/rwkv-finetune/data/processed/sample_text_document \
  --run-name rwkv7-qlora-nf4-test
```

## Model configs

Available model presets:

- `configs/model/rwkv7-0.4b.env`
- `configs/model/rwkv7-1.5b.env`
- `configs/model/rwkv7-3b.env`

Default wrappers use `rwkv7-1.5b`.

## Notes

- Scripts are aligned with current `RWKV-PEFT` CLI (`train.py`).
- For small VRAM start with QLoRA NF4 profile and `MICRO_BSZ=1`.
- Dataset for `prepare_binidx.sh` must be JSONL with one object per line.
- Main dataset focus is 1C:Enterprise programming tasks (code generation, refactoring, explanation).

## Albatross inference

There is a separate CLI wrapper for local RWKV inference via `BlinkDL/Albatross`:

```bash
python scripts/infer_albatross.py \
  --model /home/egor/code/rwkv-finetune/models/base/rwkv7-g1-1.5b-20250429-ctx4096.pth \
  --prompt "User: explain recursion in Python. Assistant:" \
  --tokens 128 \
  --batch 1 \
  --auto-clone
```

Notes:

- `--model` accepts either checkpoint prefix or `.pth` path.
- First run compiles Albatross CUDA extension and can take time.
- For `--batch > 1`, the same prompt is used for each sample.

Shortcut wrapper:

```bash
ALBATROSS_MODEL=/home/egor/code/rwkv-finetune/models/base/rwkv7-g1-1.5b-20250429-ctx4096.pth \
./scripts/run_albatross.sh --auto-clone --tokens 128
```
