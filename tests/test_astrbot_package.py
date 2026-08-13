import json
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1] / "astrbot_plugin_marvel_rivals"


class TestAstrBotPackage(unittest.TestCase):
    def test_required_plugin_files_exist(self):
        for name in ("main.py", "metadata.yaml", "_conf_schema.json", "requirements.txt"):
            self.assertTrue((PLUGIN_DIR / name).is_file(), name)

    def test_configuration_schema_is_valid_and_contains_token(self):
        schema = json.loads((PLUGIN_DIR / "_conf_schema.json").read_text(encoding="utf-8"))
        self.assertIn("MRCN_ACCESS_TOKEN", schema)
        self.assertEqual(schema["MRCN_ACCESS_TOKEN"]["default"], "")
        self.assertTrue(schema["MRCN_ACCESS_TOKEN"]["obvious_hint"])
        self.assertEqual(schema["MRCN_DEFAULT_SEASON"]["default"], 19)
        for name in ("MRCN_SUMMARY_BODY_TEMPLATE", "MRCN_CAREER_BODY_TEMPLATE", "MRCN_HERO_BODY_TEMPLATE", "MRCN_SORT_HERO_BODY_TEMPLATE", "MRCN_MATCHES_BODY_TEMPLATE"):
            self.assertIn("{season}", schema[name]["default"])

    def test_configuration_schema_uses_astrbot_types(self):
        schema = json.loads((PLUGIN_DIR / "_conf_schema.json").read_text(encoding="utf-8"))
        supported_types = {"int", "float", "bool", "string", "text", "list", "file", "object", "template_list", "dict"}
        self.assertTrue({item["type"] for item in schema.values()} <= supported_types)

    def test_metadata_and_runtime_versions_match(self):
        metadata = (PLUGIN_DIR / "metadata.yaml").read_text(encoding="utf-8")
        main = (PLUGIN_DIR / "main.py").read_text(encoding="utf-8")
        self.assertIn("name: astrbot_plugin_marvel_rivals", metadata)
        self.assertIn("version: 0.4.1", metadata)
        self.assertIn('"0.4.1"', main)

    def test_core_package_and_plugin_copy_are_synchronized(self):
        root = PLUGIN_DIR.parent
        for relative in ("models.py", "hero_names.py", "datasource/base.py", "datasource/cn.py", "services/rivals.py"):
            core = (root / "marvel_rivals_bot" / relative).read_bytes()
            bundled = (PLUGIN_DIR / "marvel_rivals_bot" / relative).read_bytes()
            self.assertEqual(core, bundled, relative)

    def test_help_documents_commands_and_season_codes(self):
        main = (PLUGIN_DIR / "main.py").read_text(encoding="utf-8")
        for text in ("/绑定漫威", "/解绑漫威", "/战绩", "/最近", "/英雄", "/对局", "S9上半赛季", "英雄名称"):
            self.assertIn(text, main)

    def test_httpx_dependency_is_declared(self):
        requirements = (PLUGIN_DIR / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("httpx", requirements)


if __name__ == "__main__":
    unittest.main()
