#!/usr/bin/env python3
"""Build trusted 1C corpus from a local repo family snapshot and git history.

TODO(add-1c-repo-family-trusted-sft): split manifest/snapshot/history/reporting logic into
dedicated modules if this builder gains more source classes or downstream integrations.
For v1 the CLI is kept self-contained to avoid spreading an unstable repo-family contract
across multiple helper modules too early.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from dataset_lifecycle import build_canonical_row, build_release_manifest, sha256_file


METHOD_PATTERN = re.compile(
    r"(?ims)^[ \t]*(?P<kind>Процедура|Функция)\s+"
    r"(?P<name>[A-Za-zА-Яа-я_][A-Za-zА-Яа-я0-9_]*)\s*\([^)]*\)"
    r"(?P<body>.*?)^[ \t]*Конец(?P<end>Процедуры|Функции)\s*;?",
)


class RepoFamilyError(RuntimeError):
    def __init__(self, reason: str, details: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.details = details or ""


@dataclass(frozen=True)
class OneCMethod:
    name: str
    kind: str
    body: str
    module_path: str
    module_type: str


@dataclass(frozen=True)
class SnapshotArtifact:
    repo_root: Path
    relpath: str
    content: str
    sha256: str
    kind: str


@dataclass
class Sample:
    user_prompt: str
    assistant_response: str
    metadata: dict[str, Any]

    @property
    def exact_hash(self) -> str:
        return sha256_text(f"{self.user_prompt}\n{self.assistant_response}")

    @property
    def near_hash(self) -> str:
        return sha256_text(normalize_near(self.assistant_response))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build trusted local repo-family corpus.")
    parser.add_argument("--family-manifest", required=True, help="Path to repo family manifest JSON.")
    parser.add_argument("--train-output", required=True, help="Output train JSONL path.")
    parser.add_argument("--dev-output", required=True, help="Output dev JSONL path.")
    parser.add_argument("--eval-output", required=True, help="Output eval JSONL path.")
    parser.add_argument("--report-output", required=True, help="Output report JSON path.")
    parser.add_argument(
        "--dataset-version",
        default="v0",
        help="Dataset version label for release manifest sections.",
    )
    parser.add_argument(
        "--hard-min-mb",
        type=int,
        default=200,
        help="Hard minimum unique corpus size in MB.",
    )
    parser.add_argument(
        "--max-history-files",
        type=int,
        default=3,
        help="Maximum changed files in a localizable history commit.",
    )
    return parser.parse_args()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_near(value: str) -> str:
    return " ".join(value.split()).lower()


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RepoFamilyError("invalid_manifest_schema", f"Expected JSON object in {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[Sample]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(build_canonical_row(row.user_prompt, row.assistant_response, row.metadata), ensure_ascii=False)
                + "\n"
            )


def validate_manifest(path: Path) -> dict[str, Any]:
    manifest = read_json(path)
    required = [
        "source_family_id",
        "repo_roots",
        "canonical_snapshot_root",
        "usage_policy",
        "license",
        "origin_ref",
    ]
    missing = [key for key in required if key not in manifest]
    if missing:
        raise RepoFamilyError("invalid_manifest_schema", ",".join(missing))
    if "training_permission" not in manifest:
        raise RepoFamilyError("missing_training_permission")
    if not manifest["training_permission"]:
        raise RepoFamilyError("training_permission_denied")
    repo_roots = [Path(item).resolve() for item in manifest["repo_roots"]]
    if not repo_roots:
        raise RepoFamilyError("missing_repo_roots")
    canonical_root = Path(manifest["canonical_snapshot_root"]).resolve()
    if canonical_root not in repo_roots:
        raise RepoFamilyError("canonical_snapshot_root_outside_family")
    for repo_root in repo_roots:
        if not repo_root.is_dir():
            raise RepoFamilyError("missing_repo_root", str(repo_root))
        if not (repo_root / ".git").exists():
            raise RepoFamilyError("repo_root_not_git", str(repo_root))
    manifest["repo_roots"] = repo_roots
    manifest["canonical_snapshot_root"] = canonical_root
    return manifest


def infer_module_type(path: str) -> str:
    lower = path.lower()
    if "manager" in lower:
        return "manager"
    if "object" in lower:
        return "object"
    if "common" in lower:
        return "common"
    return "unknown"


def is_epf_related(relpath: str) -> bool:
    return any(part.lower().endswith(".epf") for part in Path(relpath).parts)


def extract_methods_from_text(source: str) -> list[OneCMethod]:
    methods: list[OneCMethod] = []
    for match in METHOD_PATTERN.finditer(source):
        kind = match.group("kind")
        end = match.group("end")
        if kind == "Процедура" and end != "Процедуры":
            continue
        if kind == "Функция" and end != "Функции":
            continue
        full_body = (kind + " " + source[match.start("name") : match.end()]).strip()
        methods.append(
            OneCMethod(
                name=match.group("name"),
                kind=kind,
                body=full_body,
                module_path="",
                module_type="unknown",
            )
        )
    return methods


def git_output(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RepoFamilyError("git_command_failed", result.stderr.strip() or " ".join(args))
    return result.stdout.strip()


def collect_artifacts(repo_root: Path, stats: dict[str, int]) -> list[SnapshotArtifact]:
    artifacts: list[SnapshotArtifact] = []
    for path in sorted(repo_root.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix not in {".bsl", ".xml"}:
            continue
        relpath = path.relative_to(repo_root).as_posix()
        if suffix == ".bsl" and is_epf_related(relpath):
            stats["excluded_epf_paths"] += 1
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        artifacts.append(
            SnapshotArtifact(
                repo_root=repo_root,
                relpath=relpath,
                content=content,
                sha256=sha256_text(content),
                kind=suffix[1:],
            )
        )
    return artifacts


def canonicalize_artifacts(manifest: dict[str, Any], stats: dict[str, int]) -> dict[str, SnapshotArtifact]:
    grouped: dict[str, list[SnapshotArtifact]] = {}
    for repo_root in manifest["repo_roots"]:
        for artifact in collect_artifacts(repo_root, stats):
            grouped.setdefault(artifact.relpath, []).append(artifact)
    canonical: dict[str, SnapshotArtifact] = {}
    for relpath, entries in grouped.items():
        shas = {entry.sha256 for entry in entries}
        if len(shas) == 1:
            stats["identical_overlap_paths"] += 1 if len(entries) > 1 else 0
            canonical[relpath] = sorted(
                entries,
                key=lambda item: (
                    item.repo_root != manifest["canonical_snapshot_root"],
                    str(item.repo_root),
                ),
            )[0]
            continue
        stats["conflict_paths"] += 1
        chosen = next(
            (item for item in entries if item.repo_root == manifest["canonical_snapshot_root"]),
            None,
        )
        if chosen is None:
            chosen = sorted(entries, key=lambda item: str(item.repo_root))[0]
        canonical[relpath] = chosen
    stats["canonical_artifact_paths"] = len(canonical)
    return canonical


def build_snapshot_samples(
    manifest: dict[str, Any],
    canonical: dict[str, SnapshotArtifact],
) -> list[Sample]:
    samples: list[Sample] = []
    grouped_origins: dict[str, list[str]] = {}
    for repo_root in manifest["repo_roots"]:
        for path in sorted(repo_root.rglob("*.bsl")):
            relpath = path.relative_to(repo_root).as_posix()
            if is_epf_related(relpath):
                continue
            grouped_origins.setdefault(relpath, []).append(f"{repo_root}:{relpath}")
    for relpath, artifact in canonical.items():
        if artifact.kind != "bsl":
            continue
        methods = extract_methods_from_text(artifact.content)
        for method in methods:
            module_type = infer_module_type(relpath)
            suffix = "процедуру" if method.kind == "Процедура" else "функцию"
            prompt = f"Напиши {suffix} {method.name} для {module_type}-модуля 1С `{relpath}`."
            metadata = {
                "contour": "core",
                "segment": "onec_bsl",
                "lang": "ru",
                "source": "local_repo_family",
                "source_family_id": manifest["source_family_id"],
                "sample_class": "snapshot_method",
                "license": manifest["license"],
                "origin_ref": manifest["origin_ref"],
                "origin_relpath": relpath,
                "canonical_repo_root": str(artifact.repo_root),
                "alternative_origin_refs": sorted(grouped_origins.get(relpath, [])),
                "method_name": method.name,
                "module_type": module_type,
            }
            samples.append(Sample(prompt, method.body, metadata))
    return samples


def list_history_commits(repo_root: Path) -> list[str]:
    output = git_output(repo_root, "rev-list", "--reverse", "HEAD")
    return [line for line in output.splitlines() if line]


def parse_changed_methods(before_text: str, after_text: str) -> list[tuple[OneCMethod, OneCMethod]]:
    before_map = {method.name: method for method in extract_methods_from_text(before_text)}
    after_map = {method.name: method for method in extract_methods_from_text(after_text)}
    changed: list[tuple[OneCMethod, OneCMethod]] = []
    for name, after_method in after_map.items():
        before_method = before_map.get(name)
        if before_method is None:
            continue
        if normalize_near(before_method.body) != normalize_near(after_method.body):
            changed.append((before_method, after_method))
    return changed


def build_history_samples(
    manifest: dict[str, Any],
    max_history_files: int,
    stats: dict[str, int],
) -> list[Sample]:
    samples: list[Sample] = []
    for repo_root in manifest["repo_roots"]:
        commits = list_history_commits(repo_root)
        for commit in commits[1:]:
            stats["candidate_commits"] += 1
            changed_paths = [
                line
                for line in git_output(repo_root, "diff-tree", "--no-commit-id", "--name-only", "-r", commit).splitlines()
                if line
            ]
            if len(changed_paths) > max_history_files:
                stats["skipped_wide_commits"] += 1
                continue
            bsl_paths = [
                path
                for path in changed_paths
                if path.lower().endswith(".bsl") and not is_epf_related(path)
            ]
            if len(bsl_paths) != 1:
                stats["skipped_non_localizable_commits"] += 1
                continue
            relpath = bsl_paths[0]
            try:
                before_text = git_output(repo_root, "show", f"{commit}^:{relpath}")
                after_text = git_output(repo_root, "show", f"{commit}:{relpath}")
            except RepoFamilyError:
                stats["skipped_non_localizable_commits"] += 1
                continue
            changed_methods = parse_changed_methods(before_text, after_text)
            if len(changed_methods) != 1:
                stats["skipped_non_localizable_commits"] += 1
                continue
            before_method, after_method = changed_methods[0]
            commit_timestamp = int(git_output(repo_root, "show", "-s", "--format=%ct", commit))
            module_type = infer_module_type(relpath)
            prompt = (
                f"Обнови {'процедуру' if after_method.kind == 'Процедура' else 'функцию'} "
                f"{after_method.name} в 1С-модуле `{relpath}`. "
                f"Текущая версия:\n{before_method.body}"
            )
            metadata = {
                "contour": "core",
                "segment": "onec_bsl",
                "lang": "ru",
                "source": "local_repo_family",
                "source_family_id": manifest["source_family_id"],
                "sample_class": "history_method_change",
                "license": manifest["license"],
                "origin_ref": manifest["origin_ref"],
                "origin_relpath": relpath,
                "canonical_repo_root": str(repo_root),
                "alternative_origin_refs": [f"{repo_root}:{relpath}"],
                "method_name": after_method.name,
                "module_type": module_type,
                "commit_sha": commit,
                "commit_timestamp": commit_timestamp,
            }
            samples.append(Sample(prompt, after_method.body, metadata))
            stats["accepted_samples"] += 1
    return sorted(samples, key=lambda sample: sample.metadata["commit_timestamp"])


def dedup_exact(samples: list[Sample]) -> list[Sample]:
    seen: set[str] = set()
    result: list[Sample] = []
    for sample in samples:
        if sample.exact_hash in seen:
            continue
        seen.add(sample.exact_hash)
        result.append(sample)
    return result


def split_history_samples(samples: list[Sample]) -> tuple[list[Sample], list[Sample], list[Sample]]:
    total = len(samples)
    if total >= 3:
        return samples[:-2], [samples[-2]], [samples[-1]]
    if total == 2:
        return [], [samples[0]], [samples[1]]
    if total == 1:
        return [samples[0]], [], []
    return [], [], []


def remove_train_holdout_duplicates(
    train_rows: list[Sample],
    holdout_rows: list[Sample],
    stats: dict[str, int],
) -> list[Sample]:
    holdout_exact = {row.exact_hash for row in holdout_rows}
    holdout_near = {row.near_hash for row in holdout_rows}
    kept: list[Sample] = []
    for row in train_rows:
        if row.exact_hash in holdout_exact:
            stats["removed_exact_from_train"] += 1
            continue
        if row.near_hash in holdout_near:
            stats["removed_near_from_train"] += 1
            continue
        kept.append(row)
    return kept


def calculate_unique_volume(samples: list[Sample]) -> float:
    unique_by_near: dict[str, Sample] = {}
    for sample in samples:
        unique_by_near.setdefault(sample.near_hash, sample)
    total_bytes = 0
    for sample in unique_by_near.values():
        payload = json.dumps(build_canonical_row(sample.user_prompt, sample.assistant_response, sample.metadata), ensure_ascii=False)
        total_bytes += len(payload.encode("utf-8")) + 1
    return total_bytes / (1024 * 1024)


def build_release(manifest: dict[str, Any], hard_min_mb: int, max_history_files: int) -> tuple[list[Sample], list[Sample], list[Sample], dict[str, Any]]:
    snapshot_stats = {
        "excluded_epf_paths": 0,
        "identical_overlap_paths": 0,
        "conflict_paths": 0,
        "canonical_artifact_paths": 0,
    }
    history_stats = {
        "candidate_commits": 0,
        "accepted_samples": 0,
        "skipped_wide_commits": 0,
        "skipped_non_localizable_commits": 0,
    }
    split_stats = {
        "removed_exact_from_train": 0,
        "removed_near_from_train": 0,
    }

    canonical_artifacts = canonicalize_artifacts(manifest, snapshot_stats)
    snapshot_samples = dedup_exact(build_snapshot_samples(manifest, canonical_artifacts))
    history_samples = dedup_exact(build_history_samples(manifest, max_history_files, history_stats))

    history_train, history_dev, history_eval = split_history_samples(history_samples)
    train_rows = dedup_exact(snapshot_samples + history_train)
    holdout_rows = dedup_exact(history_dev + history_eval)
    train_rows = remove_train_holdout_duplicates(train_rows, holdout_rows, split_stats)

    final_samples = dedup_exact(train_rows + history_dev + history_eval)
    attained_unique_volume_mb = calculate_unique_volume(final_samples)

    quality_reasons: list[str] = []
    if attained_unique_volume_mb < hard_min_mb:
        quality_reasons.append(
            f"attained_unique_volume_mb={attained_unique_volume_mb:.4f} < hard_min_mb={hard_min_mb}"
        )

    report = {
        "source_family_id": manifest["source_family_id"],
        "inputs": {
            "repo_roots": [str(path) for path in manifest["repo_roots"]],
            "canonical_snapshot_root": str(manifest["canonical_snapshot_root"]),
            "usage_policy": manifest["usage_policy"],
            "license": manifest["license"],
            "origin_ref": manifest["origin_ref"],
        },
        "stats": {
            "snapshot": {
                **snapshot_stats,
                "snapshot_method_samples": len(snapshot_samples),
            },
            "history": history_stats,
            "split": {
                **split_stats,
                "train_rows": len(train_rows),
                "dev_rows": len(history_dev),
                "eval_rows": len(history_eval),
            },
        },
        "gates": {
            "hard_min_mb": hard_min_mb,
            "attained_unique_volume_mb": round(attained_unique_volume_mb, 6),
            "deficit_to_hard_min_mb": round(max(0.0, hard_min_mb - attained_unique_volume_mb), 6),
        },
        "quality_status": "PASS" if not quality_reasons else "FAIL",
        "quality_reasons": quality_reasons or ["quality gates passed"],
    }
    return train_rows, history_dev, history_eval, report


def failure_report(args: argparse.Namespace, reason: str, details: str = "") -> dict[str, Any]:
    return {
        "quality_status": "FAIL",
        "quality_reasons": [reason],
        "error_details": details,
        "stats": {
            "snapshot": {
                "excluded_epf_paths": 0,
                "identical_overlap_paths": 0,
                "conflict_paths": 0,
                "canonical_artifact_paths": 0,
                "snapshot_method_samples": 0,
            },
            "history": {
                "candidate_commits": 0,
                "accepted_samples": 0,
                "skipped_wide_commits": 0,
                "skipped_non_localizable_commits": 0,
            },
            "split": {
                "removed_exact_from_train": 0,
                "removed_near_from_train": 0,
                "train_rows": 0,
                "dev_rows": 0,
                "eval_rows": 0,
            },
        },
        "gates": {
            "hard_min_mb": args.hard_min_mb,
            "attained_unique_volume_mb": 0.0,
            "deficit_to_hard_min_mb": float(args.hard_min_mb),
        },
    }


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.family_manifest).resolve()
    train_output = Path(args.train_output).resolve()
    dev_output = Path(args.dev_output).resolve()
    eval_output = Path(args.eval_output).resolve()
    report_output = Path(args.report_output).resolve()

    try:
        manifest = validate_manifest(manifest_path)
        train_rows, dev_rows, eval_rows, report = build_release(
            manifest=manifest,
            hard_min_mb=args.hard_min_mb,
            max_history_files=args.max_history_files,
        )
        write_jsonl(train_output, train_rows)
        write_jsonl(dev_output, dev_rows)
        write_jsonl(eval_output, eval_rows)
        lifecycle_manifest = build_release_manifest(
            dataset_name=f"{manifest['source_family_id']}-trusted",
            dataset_version=args.dataset_version,
            created_by="scripts/build_repo_family_trusted_corpus.py",
            rows_by_split={
                "train": [build_canonical_row(row.user_prompt, row.assistant_response, row.metadata) for row in train_rows],
                "dev": [build_canonical_row(row.user_prompt, row.assistant_response, row.metadata) for row in dev_rows],
                "eval": [build_canonical_row(row.user_prompt, row.assistant_response, row.metadata) for row in eval_rows],
            },
            split_artifacts={
                "train": {"path": str(train_output), "sha256": sha256_file(train_output), "rows_total": len(train_rows)},
                "dev": {"path": str(dev_output), "sha256": sha256_file(dev_output), "rows_total": len(dev_rows)},
                "eval": {"path": str(eval_output), "sha256": sha256_file(eval_output), "rows_total": len(eval_rows)},
            },
            enforce_balance=False,
            required_eval_categories=(),
            sampling_policy={
                "ru_user_prompt_only": True,
                "task_categories": ["code_generation", "refactoring", "onec_query", "explanation_review"],
                "category_baseline": {
                    "code_generation": 0.35,
                    "refactoring": 0.35,
                    "onec_query": 0.15,
                    "explanation_review": 0.15,
                },
                "source_family_id": manifest["source_family_id"],
            },
            split_policy={
                "strategy": "source_family_temporal_lineage",
                "sibling_repos_are_single_boundary": True,
                "required_eval_categories": [],
            },
            dedup_policy={
                "exact_hash_basis": "sha256(user_prompt + assistant_response)",
                "near_hash_basis": "sha256(normalized assistant_response)",
            },
        )
        lifecycle_reasons = (
            []
            if lifecycle_manifest["quality_status"] == "PASS"
            else list(lifecycle_manifest["quality_reasons"])
        )
        report_reasons = [] if report["quality_status"] == "PASS" else list(report["quality_reasons"])
        combined_reasons = [
            *lifecycle_reasons,
            *[reason for reason in report_reasons if reason not in lifecycle_reasons],
        ]
        report = {
            **lifecycle_manifest,
            **report,
            "quality_status": "PASS" if not combined_reasons else "FAIL",
            "quality_reasons": combined_reasons or ["quality gates passed"],
        }
        write_json(report_output, report)
        print(f"train_rows: {len(train_rows)}")
        print(f"dev_rows: {len(dev_rows)}")
        print(f"eval_rows: {len(eval_rows)}")
        print(f"quality_status: {report['quality_status']}")
        print(f"report: {report_output}")
        return 0 if report["quality_status"] == "PASS" else 1
    except RepoFamilyError as exc:
        report = failure_report(args, exc.reason, exc.details)
        write_json(report_output, report)
        print(f"quality_status: FAIL")
        print(f"report: {report_output}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
