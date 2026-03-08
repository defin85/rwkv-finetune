import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class MultiSourceOneCCoreBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.script = self.repo_root / "scripts" / "build_1c_multisource_core_corpus.py"

    def write_config_export(self, root: Path) -> Path:
        config_root = root / "config_export"
        common = config_root / "CommonModules" / "CommonModule.bsl"
        common.parent.mkdir(parents=True, exist_ok=True)
        common.write_text(
            "Процедура ОбщаяПроцедура()\n"
            "    Сообщить(\"common\");\n"
            "КонецПроцедуры\n",
            encoding="utf-8",
        )
        manager = config_root / "Catalogs" / "Nomenclature" / "ManagerModule.bsl"
        manager.parent.mkdir(parents=True, exist_ok=True)
        manager.write_text(
            "Функция ПолучитьМенеджер()\n"
            "    Возврат Истина;\n"
            "КонецФункции\n",
            encoding="utf-8",
        )
        obj = config_root / "Documents" / "Order" / "ObjectModule.bsl"
        obj.parent.mkdir(parents=True, exist_ok=True)
        obj.write_text(
            "Процедура ПровестиДокумент()\n"
            "    Сообщить(\"object\");\n"
            "КонецПроцедуры\n",
            encoding="utf-8",
        )
        return config_root

    def write_jsonl(self, path: Path, rows: list[dict]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
            encoding="utf-8",
        )
        return path

    def write_manifest(
        self,
        root: Path,
        *,
        config_path: Path,
        syntax_path: Path | None,
        kb_path: Path | None,
        syntax_license: str = "internal",
    ) -> Path:
        sources: dict[str, dict[str, str]] = {
            "config_export": {
                "path": str(config_path),
                "source": "local-config-export",
                "license": "internal",
                "origin_ref": "local://config-export",
                "contour": "core",
            },
        }
        if syntax_path is not None:
            sources["syntax_helper_export"] = {
                "path": str(syntax_path),
                "source": "local-syntax-helper",
                "license": syntax_license,
                "origin_ref": "local://syntax-helper-export",
                "contour": "core",
            }
        if kb_path is not None:
            sources["kb1c_snapshot"] = {
                "path": str(kb_path),
                "source": "kb.1ci.com",
                "license": "open",
                "origin_ref": "https://kb.1ci.com/snapshot",
                "contour": "core",
            }
        manifest = {
            "dataset_name": "onec-multisource-core",
            "dataset_version": "v0",
            "sources": sources,
        }
        path = root / "multisource.manifest.json"
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def run_builder(
        self,
        workdir: Path,
        manifest_path: Path,
        *,
        hard_min_mb: int = 0,
        target_max_mb: int = 1,
    ) -> subprocess.CompletedProcess[str]:
        command = [
            "python",
            str(self.script),
            "--assembly-manifest",
            str(manifest_path),
            "--output-jsonl",
            str(workdir / "onec_core.jsonl"),
            "--report-output",
            str(workdir / "onec_core.report.json"),
            "--hard-min-mb",
            str(hard_min_mb),
            "--target-max-mb",
            str(target_max_mb),
        ]
        return subprocess.run(command, cwd=self.repo_root, check=False, text=True, capture_output=True)

    def load_jsonl(self, path: Path) -> list[dict]:
        rows: list[dict] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped:
                    rows.append(json.loads(stripped))
        return rows

    def test_builder_passes_with_three_sources_and_reports_source_contribution(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_root = self.write_config_export(root)
            syntax_path = self.write_jsonl(
                root / "syntax.jsonl",
                [
                    {
                        "title": "Новый Запрос",
                        "description": "Создаёт объект запроса 1С.",
                        "syntax": "Запрос = Новый Запрос;",
                        "example": "Запрос = Новый Запрос;\nЗапрос.Текст = \"ВЫБРАТЬ 1\";",
                    },
                    {
                        "title": "НайтиСтроки",
                        "description": "Возвращает подходящие строки таблицы значений.",
                        "syntax": "Таблица.НайтиСтроки(СтруктураОтбора)",
                    },
                ],
            )
            kb_path = self.write_jsonl(
                root / "kb.jsonl",
                [
                    {
                        "title": "Работа с документами",
                        "content": "Документы 1С поддерживают проведение и запись.",
                        "origin_ref": "https://kb.1ci.com/example/documents",
                    }
                ],
            )
            manifest = self.write_manifest(root, config_path=config_root, syntax_path=syntax_path, kb_path=kb_path)

            result = self.run_builder(root, manifest, hard_min_mb=0, target_max_mb=1)

            self.assertEqual(result.returncode, 0, msg=result.stderr + "\n" + result.stdout)
            rows = self.load_jsonl(root / "onec_core.jsonl")
            self.assertGreaterEqual(len(rows), 6)
            source_types = {row["metadata"]["source_type"] for row in rows}
            self.assertEqual(source_types, {"config_export", "syntax_helper_export", "kb1c_snapshot"})
            self.assertTrue(all(row["metadata"]["segment"] == "onec_bsl" for row in rows))
            report = json.loads((root / "onec_core.report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["quality_status"], "PASS")
            self.assertEqual(
                report["counts"]["source_type_contribution"],
                {
                    "config_export": 3,
                    "syntax_helper_export": 2,
                    "kb1c_snapshot": 1,
                },
            )

    def test_builder_fails_closed_when_required_source_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_root = self.write_config_export(root)
            syntax_path = self.write_jsonl(
                root / "syntax.jsonl",
                [{"title": "Новый Запрос", "description": "Создаёт объект запроса 1С."}],
            )
            manifest = self.write_manifest(root, config_path=config_root, syntax_path=syntax_path, kb_path=None)

            result = self.run_builder(root, manifest, hard_min_mb=0, target_max_mb=1)

            self.assertNotEqual(result.returncode, 0)
            report = json.loads((root / "onec_core.report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["quality_status"], "FAIL")
            self.assertIn("missing_required_source[kb1c_snapshot]", report["quality_reasons"])

    def test_builder_fails_closed_on_invalid_kb_domain(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_root = self.write_config_export(root)
            syntax_path = self.write_jsonl(
                root / "syntax.jsonl",
                [{"title": "Новый Запрос", "description": "Создаёт объект запроса 1С."}],
            )
            kb_path = self.write_jsonl(
                root / "kb.jsonl",
                [
                    {
                        "title": "Работа с документами",
                        "content": "Документы 1С поддерживают проведение и запись.",
                        "origin_ref": "https://example.com/not-kb",
                    }
                ],
            )
            manifest = self.write_manifest(root, config_path=config_root, syntax_path=syntax_path, kb_path=kb_path)

            result = self.run_builder(root, manifest, hard_min_mb=0, target_max_mb=1)

            self.assertNotEqual(result.returncode, 0)
            report = json.loads((root / "onec_core.report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["quality_status"], "FAIL")
            self.assertIn("invalid_kb_origin_ref", report["quality_reasons"])

    def test_builder_fails_closed_on_invalid_manifest_provenance(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_root = self.write_config_export(root)
            syntax_path = self.write_jsonl(
                root / "syntax.jsonl",
                [{"title": "Новый Запрос", "description": "Создаёт объект запроса 1С."}],
            )
            kb_path = self.write_jsonl(
                root / "kb.jsonl",
                [
                    {
                        "title": "Работа с документами",
                        "content": "Документы 1С поддерживают проведение и запись.",
                        "origin_ref": "https://kb.1ci.com/example/documents",
                    }
                ],
            )
            manifest = self.write_manifest(
                root,
                config_path=config_root,
                syntax_path=syntax_path,
                kb_path=kb_path,
                syntax_license="unknown",
            )

            result = self.run_builder(root, manifest, hard_min_mb=0, target_max_mb=1)

            self.assertNotEqual(result.returncode, 0)
            report = json.loads((root / "onec_core.report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["quality_status"], "FAIL")
            self.assertIn("invalid_source_manifest[syntax_helper_export].license", report["quality_reasons"])

    def test_builder_fails_on_volume_gate_below_minimum(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_root = self.write_config_export(root)
            syntax_path = self.write_jsonl(
                root / "syntax.jsonl",
                [{"title": "Новый Запрос", "description": "Создаёт объект запроса 1С."}],
            )
            kb_path = self.write_jsonl(
                root / "kb.jsonl",
                [
                    {
                        "title": "Работа с документами",
                        "content": "Документы 1С поддерживают проведение и запись.",
                        "origin_ref": "https://kb.1ci.com/example/documents",
                    }
                ],
            )
            manifest = self.write_manifest(root, config_path=config_root, syntax_path=syntax_path, kb_path=kb_path)

            result = self.run_builder(root, manifest, hard_min_mb=300, target_max_mb=1024)

            self.assertNotEqual(result.returncode, 0)
            report = json.loads((root / "onec_core.report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["quality_status"], "FAIL")
            self.assertTrue(any(reason.startswith("output_size_mb=") for reason in report["quality_reasons"]))


if __name__ == "__main__":
    unittest.main()
