# Project Context

## Purpose
This repository is a reproducible local workspace for RWKV v7 finetuning focused on 1C:Enterprise programming tasks on Windows + WSL2 without Docker.
It standardizes:
- environment bootstrap;
- dataset preparation (`jsonl -> binidx`) for code-centric instruction data;
- LoRA/QLoRA training with RWKV-PEFT;
- local RWKV inference via Albatross.

## Tech Stack
- Bash (`scripts/*.sh`) as the primary orchestration layer
- Python 3 + `venv` (`.venv`) for training tooling and inference wrappers
- PyTorch CUDA wheels (default index: `https://download.pytorch.org/whl/cu124`)
- RWKV-PEFT for training and JSONL-to-binidx preprocessing
- DeepSpeed and bitsandbytes for memory-efficient finetuning
- Optional Weights & Biases integration (`--wandb`)
- Git + WSL2 + NVIDIA CUDA-enabled GPU workflow

## Project Conventions

### Code Style
- Shell scripts use `#!/usr/bin/env bash` and `set -euo pipefail`.
- Script paths are repo-root relative via `ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"`.
- Required inputs are validated early (files, args, required env vars) before long-running jobs start.
- Config values are uppercase `KEY=value` in `.env` files under `configs/`.
- Python utility scripts are CLI-first (`argparse`) and use explicit argument validation.

### Architecture Patterns
- Thin-wrapper architecture: local scripts orchestrate upstream tools instead of reimplementing training internals.
- Config composition: `configs/workspace.env` stores machine/workspace settings; `configs/model/*.env` stores model-shape parameters; `configs/profile/*.env` stores training/quantization hyperparameters.
- Data pipeline: input JSONL (with `text` key) -> `scripts/prepare_binidx.sh` -> `<prefix>_text_document.{bin,idx}` -> `scripts/train*.sh`.
- Runtime outputs are organized under `runs/<run-name>/`; models/data/log artifacts are separated by directory.
- Third-party sources live in `third_party/` (RWKV-PEFT, optional Albatross clone) and are treated as upstream.

### Testing Strategy
- No formal automated unit/integration test suite is defined in this repo yet.
- Verification is operational and script-based: `./scripts/healthcheck.sh` validates GPU visibility and Python ML stack; `./scripts/prepare_binidx.sh` validates preprocessing; `./scripts/train_*.sh` and `scripts/infer_albatross.py` are smoke tests for training and inference entrypoints.
- For workflow changes, prefer short smoke runs before long training jobs.

### Git Workflow
- Current repository state is bootstrap-oriented (minimal history, no CI workflow in-repo yet).
- Working convention for contributors: keep `main` as a runnable baseline, use short-lived feature branches for scripts/config/docs updates, and keep commits small and scoped (for example: `scripts:`, `configs:`, `docs:` prefixes).
- Do not commit local/generated artifacts (`.venv`, `data/processed/*`, model checkpoints, `runs/*`, `logs/*`, `configs/workspace.env`).

## Domain Context
- Primary domain: RWKV v7 finetuning for 1C:Enterprise programming with LoRA/QLoRA profiles (`lora-bf16`, `qlora-nf4`, `qlora-int8`).
- Base model checkpoint (`.pth`) is provided manually in `models/base/`.
- Default wrappers target the `rwkv7-1.5b` model preset; additional presets exist for `rwkv7-0.4b` and `rwkv7-3b`.
- Dataset expectation: one JSON object per line with a `text` field containing 1C:Enterprise programming instructions/examples.
- Training and inference flows are intentionally separate: training uses RWKV-PEFT, while inference uses BlinkDL/Albatross via `scripts/infer_albatross.py` and `scripts/run_albatross.sh`.

## Important Constraints
- Target environment is Windows 11 + WSL2 with NVIDIA GPU support inside WSL.
- Docker is intentionally not required for this workspace.
- `nvidia-smi` should be available inside WSL before training.
- Do not install Linux NVIDIA display drivers inside WSL.
- Bootstrap and optional Albatross clone require network access (GitHub + Python package indexes).
- Training profile feasibility depends on VRAM; low-VRAM setups should start with QLoRA NF4 and low micro-batch.

## External Dependencies
- RWKV-PEFT: `https://github.com/JL-er/RWKV-PEFT.git` (default ref from `configs/workspace.env`)
- Albatross (optional inference backend): `https://github.com/BlinkDL/Albatross`
- PyTorch CUDA index: `https://download.pytorch.org/whl/cu124`
- Python packages used by the workflow: `torch`, `torchvision`, `torchaudio`, `deepspeed`, `bitsandbytes`
- Optional experiment tracking: Weights & Biases (enabled by `--wandb <project>`)
