import json
import subprocess
import tempfile
import unittest
from pathlib import Path


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
                                "source": "unit-test",
                                "license": "internal",
                                "origin_ref": "local://coding/c1",
                                "contour": "extended",
                                "segment": "coding_general",
                                "split": "train",
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
                                "source": "unit-test",
                                "license": "internal",
                                "origin_ref": "local://coding/c2",
                                "contour": "extended",
                                "segment": "coding_general",
                                "split": "train",
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
                                "source": "unit-test",
                                "license": "internal",
                                "origin_ref": "local://ru/rus1",
                                "contour": "extended",
                                "segment": "ru_identity",
                                "split": "train",
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
                                "source": "unit-test",
                                "license": "internal",
                                "origin_ref": "local://ru/rus2",
                                "contour": "extended",
                                "segment": "ru_identity",
                                "split": "train",
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
        self, workdir: Path, bsl_root: Path, coding_jsonl: Path, ru_jsonl: Path, hard_min_mb: int
    ) -> subprocess.CompletedProcess[str]:
        output_text = workdir / "release.txt"
        report = workdir / "release.report.json"
        command = [
            "python",
            str(self.script),
            "--profile",
            str(self.profile),
            "--bsl-root",
            str(bsl_root),
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


if __name__ == "__main__":
    unittest.main()
