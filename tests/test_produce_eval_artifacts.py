import json
import os
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


class ProduceEvalArtifactsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.script = self.repo_root / "scripts" / "produce_eval_artifacts.py"

    def write_chat_jsonl(self, path: Path, rows: list[tuple[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for user_prompt, assistant_response in rows:
                payload = {
                    "text": f"User: {user_prompt}\nAssistant: {assistant_response}",
                }
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def write_stub_inference_script(self, path: Path) -> None:
        path.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import argparse
                import json
                from pathlib import Path

                parser = argparse.ArgumentParser()
                parser.add_argument("--model", required=True)
                parser.add_argument("--prompt", required=True)
                parser.add_argument("--output-json", required=True)
                parser.add_argument("--tokens", type=int, default=0)
                args = parser.parse_args()

                prompt = args.prompt
                if "Рефакторни длинную процедуру" in prompt:
                    completion = "Неверный ответ"
                elif "как лучше разделить тесты" in prompt:
                    completion = "Когда нужно 'разделить тесты для CLI-утилиты', начни с чёткого критерия успеха, затем отдели быстрые unit от медленных интеграционных. Для случая 'для CLI-утилиты' проверь коды выхода и текст ошибок."
                else:
                    completion = "В задаче 'прочитать регистр накопления' зафиксируй предусловия, затем используй типизированные проверки до обращения к полям. Для 'регистр накопления' используй минимальный набор измерений в отборе."

                payload = {
                    "model": args.model,
                    "prompt": prompt,
                    "samples": [
                        {
                            "index": 0,
                            "completion": completion,
                        }
                    ],
                }
                Path(args.output_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
                """
            ),
            encoding="utf-8",
        )
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def test_producer_writes_category_artifacts_and_hard_cases_from_eval_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_name = "unit-producer"
            run_dir = self.repo_root / "runs" / run_name
            run_dir.mkdir(parents=True, exist_ok=True)
            model_path = root / "rwkv-0.pth"
            model_path.write_text("stub", encoding="utf-8")

            domain_eval = root / "domain_eval.jsonl"
            retention_eval = root / "retention_eval.jsonl"
            domain_output = root / "domain_eval.categories.json"
            retention_output = root / "retention_eval.categories.json"
            hard_cases_output = root / "hard_cases.json"
            inference_script = root / "stub_infer.py"

            self.write_chat_jsonl(
                domain_eval,
                [
                    (
                        "дай практический алгоритм: прочитать регистр накопления в 1С.",
                        "В задаче 'прочитать регистр накопления' зафиксируй предусловия, затем используй типизированные проверки до обращения к полям. Для 'регистр накопления' используй минимальный набор измерений в отборе.",
                    ),
                    (
                        "Рефакторни длинную процедуру проведения документа.",
                        "Раздели побочные эффекты и расчёт по отдельным функциям.",
                    ),
                ],
            )
            self.write_chat_jsonl(
                retention_eval,
                [
                    (
                        "как лучше разделить тесты для CLI-утилиты?",
                        "Когда нужно 'разделить тесты для CLI-утилиты', начни с чёткого критерия успеха, затем отдели быстрые unit от медленных интеграционных. Для случая 'для CLI-утилиты' проверь коды выхода и текст ошибок.",
                    ),
                ],
            )
            self.write_stub_inference_script(inference_script)

            result = subprocess.run(
                [
                    "python",
                    str(self.script),
                    "--run-name",
                    run_name,
                    "--model",
                    str(model_path),
                    "--domain-eval-jsonl",
                    str(domain_eval),
                    "--retention-eval-jsonl",
                    str(retention_eval),
                    "--domain-output",
                    str(domain_output),
                    "--retention-output",
                    str(retention_output),
                    "--hard-cases-output",
                    str(hard_cases_output),
                    "--inference-script",
                    str(inference_script),
                    "--tokens",
                    "32",
                ],
                cwd=self.repo_root,
                text=True,
                capture_output=True,
                check=False,
                env={**os.environ, "USE_WORKSPACE_ENV": "0"},
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr + "\n" + result.stdout)

            domain_payload = json.loads(domain_output.read_text(encoding="utf-8"))
            retention_payload = json.loads(retention_output.read_text(encoding="utf-8"))
            hard_cases = json.loads(hard_cases_output.read_text(encoding="utf-8"))

            self.assertEqual(domain_payload["code_generation"]["verdict"], "PASS")
            self.assertEqual(domain_payload["refactoring"]["verdict"], "FAIL")
            self.assertEqual(domain_payload["refactoring"]["failures_total"], 1)
            self.assertEqual(retention_payload["ru_general"]["verdict"], "PASS")
            self.assertEqual(len(hard_cases), 1)
            self.assertEqual(hard_cases[0]["suite"], "domain_eval")
            self.assertEqual(hard_cases[0]["category"], "refactoring")

            if run_dir.exists():
                for path in run_dir.glob("*"):
                    if path.is_file():
                        path.unlink()
                run_dir.rmdir()


if __name__ == "__main__":
    unittest.main()
