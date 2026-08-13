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

    def test_metadata_and_runtime_versions_match(self):
        metadata = (PLUGIN_DIR / "metadata.yaml").read_text(encoding="utf-8")
        main = (PLUGIN_DIR / "main.py").read_text(encoding="utf-8")
        self.assertIn("name: astrbot_plugin_marvel_rivals", metadata)
        self.assertIn("version: 0.2.1", metadata)
        self.assertIn('"0.2.1"', main)

    def test_httpx_dependency_is_declared(self):
        requirements = (PLUGIN_DIR / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("httpx", requirements)


if __name__ == "__main__":
    unittest.main()
