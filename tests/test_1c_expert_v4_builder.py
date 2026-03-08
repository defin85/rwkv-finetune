import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.dataset_lifecycle import build_canonical_row


class OneCExpertV4BuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.script = self.repo_root / "scripts" / "build_1c_expert_v4_dataset.py"
        self.profile = self.repo_root / "configs" / "dataset" / "1c-expert-v4.profile.json"

    def write_bsl_modules(self, root: Path, include_manager: bool = True) -> None:
        common = root / "CommonModules" / "CommonModule.bsl"
        common.parent.mkdir(parents=True, exist_ok=True)
        common.write_text(
            "Процедура ОбщаяПроцедура()\n"
            "    Сообщить(\"common\");\n"
            "КонецПроцедуры\n",
            encoding="utf-8",
        )

        if include_manager:
            manager = root / "Catalogs" / "Nomenclature" / "ManagerModule.bsl"
            manager.parent.mkdir(parents=True, exist_ok=True)
            manager.write_text(
                "Функция ПолучитьМенеджер()\n"
                "    Возврат Истина;\n"
                "КонецФункции\n",
                encoding="utf-8",
            )

        obj = root / "Documents" / "Order" / "ObjectModule.bsl"
        obj.parent.mkdir(parents=True, exist_ok=True)
        obj.write_text(
            "Процедура ПровестиДокумент()\n"
            "    Сообщить(\"object\");\n"
            "КонецПроцедуры\n",
            encoding="utf-8",
        )

    def write_canonical_jsonl_inputs(
        self,
        root: Path,
        *,
        coding_prompts: tuple[str, str] = ("Напиши функцию C1", "Напиши функцию C2"),
        ru_prompts: tuple[str, str] = ("Объясни RUS1", "Объясни RUS2"),
        coding_sources: tuple[str, str] = ("unit-test", "unit-test"),
        ru_sources: tuple[str, str] = ("unit-test", "unit-test"),
        coding_metadata_overrides: tuple[dict | None, dict | None] = (None, None),
        ru_metadata_overrides: tuple[dict | None, dict | None] = (None, None),
    ) -> tuple[Path, Path]:
        coding = root / "coding.jsonl"
        ru = root / "ru.jsonl"
        coding.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "user_prompt": coding_prompts[0],
                            "assistant_response": "def c1():\n    return 'c1'",
                            "metadata": {
                                "source": coding_sources[0],
                                "license": "internal",
                                "origin_ref": "local://coding/c1",
                                "contour": "extended",
                                "segment": "coding_general",
                                "split": "train",
                                "quality_rationale": "Synthetic coding fixture for unit testing.",
                                **(coding_metadata_overrides[0] or {}),
                            },
                        },
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        {
                            "user_prompt": coding_prompts[1],
                            "assistant_response": "def c2():\n    return 'c2'",
                            "metadata": {
                                "source": coding_sources[1],
                                "license": "internal",
                                "origin_ref": "local://coding/c2",
                                "contour": "extended",
                                "segment": "coding_general",
                                "split": "train",
                                "quality_rationale": "Synthetic coding fixture for unit testing.",
                                **(coding_metadata_overrides[1] or {}),
                            },
                        },
                        ensure_ascii=False,
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        ru.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "user_prompt": ru_prompts[0],
                            "assistant_response": "Это ответ ANS1",
                            "metadata": {
                                "source": ru_sources[0],
                                "license": "internal",
                                "origin_ref": "local://ru/rus1",
                                "contour": "extended",
                                "segment": "ru_identity",
                                "split": "train",
                                "quality_rationale": "Synthetic RU fixture for unit testing.",
                                **(ru_metadata_overrides[0] or {}),
                            },
                        },
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        {
                            "user_prompt": ru_prompts[1],
                            "assistant_response": "Это ответ ANS2",
                            "metadata": {
                                "source": ru_sources[1],
                                "license": "internal",
                                "origin_ref": "local://ru/rus2",
                                "contour": "extended",
                                "segment": "ru_identity",
                                "split": "train",
                                "quality_rationale": "Synthetic RU fixture for unit testing.",
                                **(ru_metadata_overrides[1] or {}),
                            },
                        },
                        ensure_ascii=False,
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return coding, ru

    def run_builder(
        self,
        workdir: Path,
        bsl_root: Path | None,
        coding_jsonl: Path,
        ru_jsonl: Path,
        hard_min_mb: int,
        *,
        bsl_source: str = "unit-test-bsl",
        bsl_license: str = "internal",
        bsl_origin_ref: str = "local://onec/unit",
        bsl_contour: str = "core",
        onec_core_jsonl: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        output_text = workdir / "release.txt"
        report = workdir / "release.report.json"
        command = [
            "python",
            str(self.script),
            "--profile",
            str(self.profile),
            "--coding-jsonl",
            str(coding_jsonl),
            "--ru-jsonl",
            str(ru_jsonl),
            "--output-text",
            str(output_text),
            "--report-output",
            str(report),
            "--seed",
            "42",
            "--hard-min-mb",
            str(hard_min_mb),
        ]
        if onec_core_jsonl is not None:
            command.extend(["--onec-core-jsonl", str(onec_core_jsonl)])
        else:
            command.extend(
                [
                    "--bsl-root",
                    str(bsl_root),
                    "--bsl-source",
                    bsl_source,
                    "--bsl-license",
                    bsl_license,
                    "--bsl-origin-ref",
                    bsl_origin_ref,
                    "--bsl-contour",
                    bsl_contour,
                ]
            )
        return subprocess.run(command, cwd=self.repo_root, check=False, text=True, capture_output=True)

    def test_pipeline_passes_with_all_module_types_and_zero_hard_min(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            bsl_root = root / "onec"
            bsl_root.mkdir(parents=True, exist_ok=True)
            self.write_bsl_modules(bsl_root, include_manager=True)
            coding, ru = self.write_canonical_jsonl_inputs(root)
            result = self.run_builder(root, bsl_root, coding, ru, hard_min_mb=0)
            self.assertEqual(result.returncode, 0, msg=result.stderr + "\n" + result.stdout)

            report = json.loads((root / "release.report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["quality_status"], "PASS")
            text = (root / "release.txt").read_text(encoding="utf-8")
            self.assertIn("Instruction:", text)
            self.assertIn("Response:", text)
            self.assertIn("<|endoftext|>", text)
            self.assertNotEqual(text.find("Instruction: Напиши функцию C"), -1)
            self.assertNotEqual(text.find("Instruction: Объясни RUS"), -1)
            self.assertNotEqual(text.find("Instruction: Напиши"), -1)

    def test_pipeline_fails_when_module_coverage_missing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            bsl_root = root / "onec"
            bsl_root.mkdir(parents=True, exist_ok=True)
            self.write_bsl_modules(bsl_root, include_manager=False)
            coding, ru = self.write_canonical_jsonl_inputs(root)
            result = self.run_builder(root, bsl_root, coding, ru, hard_min_mb=0)
            self.assertNotEqual(result.returncode, 0)
            report = json.loads((root / "release.report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["quality_status"], "FAIL")
            self.assertIn("module_coverage_missing:manager", report["quality_reasons"])

    def test_pipeline_fails_on_hard_min_size_gate(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            bsl_root = root / "onec"
            bsl_root.mkdir(parents=True, exist_ok=True)
            self.write_bsl_modules(bsl_root, include_manager=True)
            coding, ru = self.write_canonical_jsonl_inputs(root)
            result = self.run_builder(root, bsl_root, coding, ru, hard_min_mb=1)
            self.assertNotEqual(result.returncode, 0)
            report = json.loads((root / "release.report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["quality_status"], "FAIL")
            self.assertTrue(
                any(reason.startswith("output_size_mb=") for reason in report["quality_reasons"])
            )

    def test_pipeline_accepts_canonical_user_prompt_assistant_response_rows(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            bsl_root = root / "onec"
            bsl_root.mkdir(parents=True, exist_ok=True)
            self.write_bsl_modules(bsl_root, include_manager=True)
            coding, ru = self.write_canonical_jsonl_inputs(root)
            result = self.run_builder(root, bsl_root, coding, ru, hard_min_mb=0)
            self.assertEqual(result.returncode, 0, msg=result.stderr + "\n" + result.stdout)
            text = (root / "release.txt").read_text(encoding="utf-8")
            self.assertIn("Instruction: Напиши функцию C1", text)
            self.assertIn("Instruction: Объясни RUS1", text)

    def test_pipeline_reports_actual_mix_and_shuffle_metadata(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            bsl_root = root / "onec"
            bsl_root.mkdir(parents=True, exist_ok=True)
            self.write_bsl_modules(bsl_root, include_manager=True)
            coding, ru = self.write_canonical_jsonl_inputs(root)
            result = self.run_builder(root, bsl_root, coding, ru, hard_min_mb=0)
            self.assertEqual(result.returncode, 0, msg=result.stderr + "\n" + result.stdout)

            report = json.loads((root / "release.report.json").read_text(encoding="utf-8"))
            self.assertEqual(
                report["counts"]["actual_mix"],
                {
                    "onec_bsl": 0.5,
                    "coding_general": 0.333333,
                    "ru_identity": 0.166667,
                },
            )
            self.assertEqual(report["shuffle"]["strategy"], "segment_interleave_shuffle")
            self.assertEqual(report["shuffle"]["seed"], 42)
            self.assertEqual(
                report["shuffle"]["segment_order_preview"],
                [
                    "onec_bsl",
                    "coding_general",
                    "ru_identity",
                    "coding_general",
                    "onec_bsl",
                    "onec_bsl",
                ],
            )
            self.assertGreater(report["shuffle"]["segment_switches"], 0)
            self.assertTrue(report["shuffle"]["segment_order_sha256"])

    def test_pipeline_fails_closed_on_non_russian_prompt(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            bsl_root = root / "onec"
            bsl_root.mkdir(parents=True, exist_ok=True)
            self.write_bsl_modules(bsl_root, include_manager=True)
            coding, ru = self.write_canonical_jsonl_inputs(
                root,
                coding_prompts=("Write function C1", "Напиши функцию C2"),
            )
            result = self.run_builder(root, bsl_root, coding, ru, hard_min_mb=0)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("user_prompt_not_russian", result.stderr + result.stdout)

    def test_pipeline_fails_closed_on_non_allowlisted_external_source_without_quality_rationale(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            bsl_root = root / "onec"
            bsl_root.mkdir(parents=True, exist_ok=True)
            self.write_bsl_modules(bsl_root, include_manager=True)
            coding, ru = self.write_canonical_jsonl_inputs(
                root,
                coding_sources=("custom/external-coding", "custom/external-coding"),
                coding_metadata_overrides=(
                    {
                        "license": "open",
                        "origin_ref": "https://huggingface.co/datasets/custom/external-coding",
                        "quality_rationale": "",
                    },
                    {
                        "license": "open",
                        "origin_ref": "https://huggingface.co/datasets/custom/external-coding",
                        "quality_rationale": "",
                    },
                ),
            )
            result = self.run_builder(root, bsl_root, coding, ru, hard_min_mb=0)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "non_allowlisted_source_missing_quality_rationale",
                result.stderr + result.stdout,
            )

    def test_pipeline_fails_closed_on_missing_provenance_metadata(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            bsl_root = root / "onec"
            bsl_root.mkdir(parents=True, exist_ok=True)
            self.write_bsl_modules(bsl_root, include_manager=True)
            coding, ru = self.write_canonical_jsonl_inputs(
                root,
                coding_metadata_overrides=({"license": "unknown"}, None),
            )
            result = self.run_builder(root, bsl_root, coding, ru, hard_min_mb=0)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid_metadata.license", result.stderr + result.stdout)

    def test_pipeline_fails_closed_on_invalid_onec_bsl_provenance_metadata(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            bsl_root = root / "onec"
            bsl_root.mkdir(parents=True, exist_ok=True)
            self.write_bsl_modules(bsl_root, include_manager=True)
            coding, ru = self.write_canonical_jsonl_inputs(root)
            result = self.run_builder(
                root,
                bsl_root,
                coding,
                ru,
                hard_min_mb=0,
                bsl_license="unknown",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid_metadata.license", result.stderr + result.stdout)

    def test_pipeline_accepts_multisource_onec_core_jsonl_handoff(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            onec_core_jsonl = root / "onec_core.jsonl"
            onec_rows = [
                build_canonical_row(
                    "Напиши процедуру для ОбщаяПроцедура в 1С.",
                    "Процедура ОбщаяПроцедура()\n    Сообщить(\"common\");\nКонецПроцедуры\n",
                    {
                        "source": "local-config-export",
                        "license": "internal",
                        "origin_ref": "local://config-export#CommonModules/CommonModule.bsl",
                        "contour": "core",
                        "segment": "onec_bsl",
                        "split": "train",
                        "source_type": "config_export",
                        "module_type": "common",
                    },
                ),
                build_canonical_row(
                    "Объясни синтаксис 1С для «Новый Запрос».",
                    "Описание:\nСоздаёт объект запроса 1С.\n\nСинтаксис:\nЗапрос = Новый Запрос;",
                    {
                        "source": "local-syntax-helper",
                        "license": "internal",
                        "origin_ref": "local://syntax-helper-export#new-query",
                        "contour": "core",
                        "segment": "onec_bsl",
                        "split": "train",
                        "source_type": "syntax_helper_export",
                        "module_type": "manager",
                    },
                ),
                build_canonical_row(
                    "Объясни материал 1С по теме «Работа с документами».",
                    "Документы 1С поддерживают проведение и запись.",
                    {
                        "source": "kb.1ci.com",
                        "license": "open",
                        "origin_ref": "https://kb.1ci.com/example/documents",
                        "contour": "core",
                        "segment": "onec_bsl",
                        "split": "train",
                        "source_type": "kb1c_snapshot",
                        "module_type": "object",
                    },
                ),
            ]
            onec_core_jsonl.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in onec_rows) + "\n",
                encoding="utf-8",
            )
            coding, ru = self.write_canonical_jsonl_inputs(root)
            result = self.run_builder(
                root,
                None,
                coding,
                ru,
                hard_min_mb=0,
                onec_core_jsonl=onec_core_jsonl,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr + "\n" + result.stdout)
            text = (root / "release.txt").read_text(encoding="utf-8")
            self.assertIn("Instruction: Объясни синтаксис 1С для", text)
            self.assertIn("Instruction: Объясни материал 1С по теме", text)
            report = json.loads((root / "release.report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["quality_status"], "PASS")


if __name__ == "__main__":
    unittest.main()
