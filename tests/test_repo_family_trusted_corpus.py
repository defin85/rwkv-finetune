import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class RepoFamilyTrustedCorpusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.script = self.repo_root / "scripts" / "build_repo_family_trusted_corpus.py"

    def git(self, cwd: Path, *args: str, env: dict[str, str] | None = None) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
        if result.returncode != 0:
            self.fail(f"git {' '.join(args)} failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        return result.stdout.strip()

    def init_repo(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self.git(path, "init", "-b", "main")
        self.git(path, "config", "user.email", "tests@example.com")
        self.git(path, "config", "user.name", "Repo Family Tests")

    def commit_all(self, path: Path, message: str, timestamp: str) -> str:
        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = timestamp
        env["GIT_COMMITTER_DATE"] = timestamp
        self.git(path, "add", ".")
        self.git(path, "commit", "-m", message, env=env)
        return self.git(path, "rev-parse", "HEAD")

    def write_file(self, root: Path, relpath: str, content: str) -> None:
        target = root / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def write_manifest(
        self,
        root: Path,
        repo_roots: list[Path],
        canonical_snapshot_root: Path,
        include_permission: bool = True,
    ) -> Path:
        manifest = {
            "source_family_id": "rolf-family",
            "repo_roots": [str(item) for item in repo_roots],
            "canonical_snapshot_root": str(canonical_snapshot_root),
            "usage_policy": "internal-training",
            "license": "internal",
            "origin_ref": "local://rolf-family",
        }
        if include_permission:
            manifest["training_permission"] = True
        path = root / "repo-family.manifest.json"
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def run_builder(
        self,
        workdir: Path,
        manifest_path: Path,
        hard_min_mb: int = 0,
        max_history_files: int = 3,
    ) -> subprocess.CompletedProcess[str]:
        command = [
            "python",
            str(self.script),
            "--family-manifest",
            str(manifest_path),
            "--train-output",
            str(workdir / "train.jsonl"),
            "--dev-output",
            str(workdir / "dev.jsonl"),
            "--eval-output",
            str(workdir / "eval.jsonl"),
            "--report-output",
            str(workdir / "release.report.json"),
            "--hard-min-mb",
            str(hard_min_mb),
            "--max-history-files",
            str(max_history_files),
        ]
        return subprocess.run(command, cwd=self.repo_root, text=True, capture_output=True, check=False)

    def load_jsonl(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        rows: list[dict] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                rows.append(json.loads(stripped))
        return rows

    def test_manifest_without_training_permission_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            repo = root / "repo"
            self.init_repo(repo)
            self.write_file(
                repo,
                "CommonModules/CommonModule.bsl",
                "Процедура Тест()\n    Сообщить(\"ok\");\nКонецПроцедуры\n",
            )
            self.commit_all(repo, "initial", "2026-01-01T00:00:00+0000")
            manifest = self.write_manifest(root, [repo], repo, include_permission=False)

            result = self.run_builder(root, manifest, hard_min_mb=0)

            self.assertNotEqual(result.returncode, 0)
            report = json.loads((root / "release.report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["quality_status"], "FAIL")
            self.assertIn("missing_training_permission", report["quality_reasons"])

    def test_identical_snapshot_overlap_is_canonicalized_with_alternative_origins(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            repo_a = root / "repo-a"
            repo_b = root / "repo-b"
            self.init_repo(repo_a)
            self.init_repo(repo_b)
            source = (
                "Процедура ОбщаяПроцедура()\n"
                "    Сообщить(\"shared\");\n"
                "КонецПроцедуры\n"
            )
            self.write_file(repo_a, "CommonModules/CommonModule.bsl", source)
            self.write_file(repo_b, "CommonModules/CommonModule.bsl", source)
            self.commit_all(repo_a, "initial-a", "2026-01-01T00:00:00+0000")
            self.commit_all(repo_b, "initial-b", "2026-01-01T00:00:10+0000")
            manifest = self.write_manifest(root, [repo_a, repo_b], repo_a)

            result = self.run_builder(root, manifest, hard_min_mb=0)

            self.assertEqual(result.returncode, 0, msg=result.stderr + "\n" + result.stdout)
            train_rows = self.load_jsonl(root / "train.jsonl")
            self.assertEqual(len(train_rows), 1)
            row = train_rows[0]
            self.assertEqual(row["metadata"]["sample_class"], "snapshot_method")
            self.assertEqual(row["metadata"]["contour"], "core")
            self.assertEqual(row["metadata"]["segment"], "onec_bsl")
            self.assertEqual(len(row["metadata"]["alternative_origin_refs"]), 2)
            self.assertIn("Напиши", row["user_prompt"])
            report = json.loads((root / "release.report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["stats"]["snapshot"]["identical_overlap_paths"], 1)

    def test_conflicting_snapshot_uses_canonical_root_and_reports_conflict(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            repo_a = root / "repo-a"
            repo_b = root / "repo-b"
            self.init_repo(repo_a)
            self.init_repo(repo_b)
            self.write_file(
                repo_a,
                "Catalogs/Nomenclature/ManagerModule.bsl",
                "Функция Получить()\n    Возврат 1;\nКонецФункции\n",
            )
            self.write_file(
                repo_b,
                "Catalogs/Nomenclature/ManagerModule.bsl",
                "Функция Получить()\n    Возврат 2;\nКонецФункции\n",
            )
            self.commit_all(repo_a, "initial-a", "2026-01-01T00:00:00+0000")
            self.commit_all(repo_b, "initial-b", "2026-01-01T00:00:10+0000")
            manifest = self.write_manifest(root, [repo_a, repo_b], repo_a)

            result = self.run_builder(root, manifest, hard_min_mb=0)

            self.assertEqual(result.returncode, 0, msg=result.stderr + "\n" + result.stdout)
            train_rows = self.load_jsonl(root / "train.jsonl")
            self.assertEqual(len(train_rows), 1)
            self.assertIn("Возврат 1;", train_rows[0]["assistant_response"])
            report = json.loads((root / "release.report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["stats"]["snapshot"]["conflict_paths"], 1)

    def test_epf_related_bsl_is_excluded_from_trusted_v1(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            repo = root / "repo"
            self.init_repo(repo)
            self.write_file(
                repo,
                "CommonModules/CommonModule.bsl",
                "Процедура Нормальная()\n    Сообщить(\"ok\");\nКонецПроцедуры\n",
            )
            self.write_file(
                repo,
                "ExternalReports/Demo.epf/Module.bsl",
                "Процедура Внешняя()\n    Сообщить(\"epf\");\nКонецПроцедуры\n",
            )
            self.commit_all(repo, "initial", "2026-01-01T00:00:00+0000")
            manifest = self.write_manifest(root, [repo], repo)

            result = self.run_builder(root, manifest, hard_min_mb=0)

            self.assertEqual(result.returncode, 0, msg=result.stderr + "\n" + result.stdout)
            train_rows = self.load_jsonl(root / "train.jsonl")
            self.assertEqual(len(train_rows), 1)
            self.assertNotIn(".epf", train_rows[0]["metadata"]["origin_relpath"])
            report = json.loads((root / "release.report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["stats"]["snapshot"]["excluded_epf_paths"], 1)

    def test_history_holdout_removes_duplicate_snapshot_from_train(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            repo = root / "repo"
            self.init_repo(repo)
            relpath = "Documents/Order/ObjectModule.bsl"
            self.write_file(
                repo,
                relpath,
                "Функция Рассчитать()\n    Возврат 1;\nКонецФункции\n",
            )
            self.commit_all(repo, "initial", "2026-01-01T00:00:00+0000")
            self.write_file(
                repo,
                relpath,
                "Функция Рассчитать()\n    Возврат 2;\nКонецФункции\n",
            )
            self.commit_all(repo, "change-two", "2026-01-02T00:00:00+0000")
            self.write_file(
                repo,
                relpath,
                "Функция Рассчитать()\n    Возврат 3;\nКонецФункции\n",
            )
            self.commit_all(repo, "change-three", "2026-01-03T00:00:00+0000")
            manifest = self.write_manifest(root, [repo], repo)

            result = self.run_builder(root, manifest, hard_min_mb=0)

            self.assertEqual(result.returncode, 0, msg=result.stderr + "\n" + result.stdout)
            train_rows = self.load_jsonl(root / "train.jsonl")
            dev_rows = self.load_jsonl(root / "dev.jsonl")
            eval_rows = self.load_jsonl(root / "eval.jsonl")
            self.assertEqual(len(dev_rows), 1)
            self.assertEqual(len(eval_rows), 1)
            self.assertTrue(
                any(row["metadata"]["sample_class"] == "history_method_change" for row in dev_rows + eval_rows)
            )
            self.assertFalse(any("Возврат 3;" in row["assistant_response"] for row in train_rows))
            report = json.loads((root / "release.report.json").read_text(encoding="utf-8"))
            removed_total = (
                report["stats"]["split"]["removed_exact_from_train"]
                + report["stats"]["split"]["removed_near_from_train"]
            )
            self.assertGreaterEqual(removed_total, 1)

    def test_wide_history_commit_is_skipped_with_reason(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            repo = root / "repo"
            self.init_repo(repo)
            for index in range(5):
                self.write_file(
                    repo,
                    f"CommonModules/Module{index}.bsl",
                    f"Процедура Метод{index}()\n    Сообщить(\"{index}\");\nКонецПроцедуры\n",
                )
            self.commit_all(repo, "initial", "2026-01-01T00:00:00+0000")
            for index in range(5):
                self.write_file(
                    repo,
                    f"CommonModules/Module{index}.bsl",
                    f"Процедура Метод{index}()\n    Сообщить(\"changed-{index}\");\nКонецПроцедуры\n",
                )
            self.commit_all(repo, "wide-change", "2026-01-02T00:00:00+0000")
            manifest = self.write_manifest(root, [repo], repo)

            result = self.run_builder(root, manifest, hard_min_mb=0, max_history_files=3)

            self.assertEqual(result.returncode, 0, msg=result.stderr + "\n" + result.stdout)
            report = json.loads((root / "release.report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["stats"]["history"]["skipped_wide_commits"], 1)

    def test_hard_minimum_gate_blocks_small_release(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            repo = root / "repo"
            self.init_repo(repo)
            self.write_file(
                repo,
                "CommonModules/CommonModule.bsl",
                "Процедура Тест()\n    Сообщить(\"ok\");\nКонецПроцедуры\n",
            )
            self.commit_all(repo, "initial", "2026-01-01T00:00:00+0000")
            manifest = self.write_manifest(root, [repo], repo)

            result = self.run_builder(root, manifest, hard_min_mb=1)

            self.assertNotEqual(result.returncode, 0)
            report = json.loads((root / "release.report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["quality_status"], "FAIL")
            self.assertTrue(
                any(reason.startswith("attained_unique_volume_mb=") for reason in report["quality_reasons"])
            )


if __name__ == "__main__":
    unittest.main()
