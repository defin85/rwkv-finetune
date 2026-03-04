import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


def load_module() -> ModuleType:
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "build_1c_expert_v4_dataset.py"
    spec = importlib.util.spec_from_file_location("build_1c_expert_v4_dataset", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class OneCBSLExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_extract_methods_returns_one_record_per_procedure_or_function(self):
        source = """
Процедура ОбновитьОстатки(Параметр)
    Сообщить("ok");
КонецПроцедуры

Функция РассчитатьИтог(Сумма, НДС)
    Возврат Сумма + НДС;
КонецФункции
"""
        methods = self.module.extract_methods_from_text(source)
        self.assertEqual(len(methods), 2)
        self.assertEqual(methods[0].name, "ОбновитьОстатки")
        self.assertEqual(methods[0].kind, "Процедура")
        self.assertIn("КонецПроцедуры", methods[0].body)
        self.assertEqual(methods[1].name, "РассчитатьИтог")
        self.assertEqual(methods[1].kind, "Функция")
        self.assertIn("КонецФункции", methods[1].body)

    def test_extract_methods_scans_multiple_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            first = root / "CommonModules" / "A.bsl"
            second = root / "Documents" / "Order" / "ObjectModule.bsl"
            first.parent.mkdir(parents=True, exist_ok=True)
            second.parent.mkdir(parents=True, exist_ok=True)
            first.write_text(
                "Процедура Синхронизировать()\n"
                "    Сообщить(\"sync\");\n"
                "КонецПроцедуры\n",
                encoding="utf-8",
            )
            second.write_text(
                "Функция Вычислить()\n"
                "    Возврат 42;\n"
                "КонецФункции\n",
                encoding="utf-8",
            )

            records = self.module.collect_onec_methods(root)
            self.assertEqual(len(records), 2)
            self.assertEqual({row.name for row in records}, {"Синхронизировать", "Вычислить"})


if __name__ == "__main__":
    unittest.main()
