#!/usr/bin/env python3
"""CLI inference wrapper around BlinkDL/Albatross for RWKV models."""

from __future__ import annotations

import argparse
import random
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Run RWKV inference via Albatross.")
    parser.add_argument(
        "--model",
        required=True,
        help="Path to checkpoint prefix or .pth file (example: /path/rwkv7-g1-1.5b-...-ctx4096)",
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help="Input prompt.",
    )
    parser.add_argument(
        "--tokens",
        type=int,
        default=128,
        help="Number of generated tokens per sequence.",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=1,
        help="Batch size. Uses the same prompt for each sample.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=1.0,
        help="Temperature for simple sampler.",
    )
    parser.add_argument(
        "--noise",
        type=float,
        default=0.0,
        help="Uniform noise added to logits before argmax (0 = greedy).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed.",
    )
    parser.add_argument(
        "--albatross-dir",
        default=str(root / "third_party" / "Albatross"),
        help="Local Albatross directory.",
    )
    parser.add_argument(
        "--tokenizer",
        default="",
        help="Tokenizer file. Default: <albatross-dir>/reference/rwkv_vocab_v20230424.txt",
    )
    parser.add_argument(
        "--auto-clone",
        action="store_true",
        help="Clone Albatross automatically if directory is missing.",
    )
    return parser.parse_args()


def normalize_model_prefix(model_arg: str) -> str:
    model = Path(model_arg).expanduser()
    model_str = str(model)
    if model_str.endswith(".pth"):
        model_str = model_str[:-4]
    pth = Path(model_str + ".pth")
    if not pth.exists():
        raise FileNotFoundError(f"Model checkpoint not found: {pth}")
    return model_str


def ensure_albatross_repo(albatross_dir: Path, auto_clone: bool) -> None:
    if albatross_dir.joinpath("reference", "rwkv7.py").exists():
        return
    if not auto_clone:
        raise FileNotFoundError(
            f"Albatross not found at {albatross_dir}. "
            "Use --auto-clone or clone manually: git clone https://github.com/BlinkDL/Albatross <dir>"
        )
    albatross_dir.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--depth", "1", "https://github.com/BlinkDL/Albatross", str(albatross_dir)],
        check=True,
    )


def set_seed(seed: int) -> None:
    import numpy as np  # pylint: disable=import-outside-toplevel
    import torch  # pylint: disable=import-outside-toplevel

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)


def main() -> int:
    args = parse_args()

    import torch  # pylint: disable=import-outside-toplevel

    if args.tokens < 0:
        raise ValueError("--tokens must be >= 0")
    if args.batch < 1:
        raise ValueError("--batch must be >= 1")
    if args.temperature <= 0:
        raise ValueError("--temperature must be > 0")

    albatross_dir = Path(args.albatross_dir).expanduser().resolve()
    ensure_albatross_repo(albatross_dir, auto_clone=args.auto_clone)

    model_prefix = normalize_model_prefix(args.model)
    tokenizer_path = (
        Path(args.tokenizer).expanduser().resolve()
        if args.tokenizer
        else albatross_dir / "reference" / "rwkv_vocab_v20230424.txt"
    )
    if not tokenizer_path.exists():
        raise FileNotFoundError(f"Tokenizer not found: {tokenizer_path}")

    set_seed(args.seed)

    # Albatross modules are repo-relative imports.
    sys.path.insert(0, str(albatross_dir))
    from reference.rwkv7 import RWKV_x070  # pylint: disable=import-outside-toplevel
    from reference.utils import (  # pylint: disable=import-outside-toplevel
        TRIE_TOKENIZER,
        sampler_simple_batch,
    )

    model_args = SimpleNamespace(vocab_size=65536, head_size=64, MODEL_NAME=model_prefix)
    print(f"Loading model: {model_prefix}.pth")
    model = RWKV_x070(model_args)
    tokenizer = TRIE_TOKENIZER(str(tokenizer_path))

    prompts = [args.prompt for _ in range(args.batch)]
    state = model.generate_zero_state(args.batch)
    encoded = [tokenizer.encode(p) for p in prompts]

    print(f"Prefill: batch={args.batch}")
    out = model.forward_batch(encoded, state)

    generated_tokens = [[] for _ in range(args.batch)]
    if args.tokens > 0:
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        for _ in range(args.tokens):
            next_tokens = sampler_simple_batch(
                out, noise=args.noise, temp=args.temperature
            ).tolist()
            for i in range(args.batch):
                generated_tokens[i].extend(next_tokens[i])
            out = model.forward_batch(next_tokens, state)
        torch.cuda.synchronize()
        dt = time.perf_counter() - t0
        tps = (args.tokens * args.batch) / dt if dt > 0 else 0.0
        print(f"Decode done: {args.tokens} tokens/seq, {tps:.2f} tok/s total")

    print()
    for i in range(args.batch):
        completion = tokenizer.decode(generated_tokens[i], utf8_errors="ignore")
        print(f"[sample {i}]")
        print(prompts[i] + completion)
        print("-" * 80)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
