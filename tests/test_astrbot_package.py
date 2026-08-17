import json
import subprocess
import sys
import unittest
from pathlib import Path
import zipfile

from tools.release import validate_source


PLUGIN_DIR = Path(__file__).resolve().parents[1]


class TestAstrBotPackage(unittest.TestCase):
    def test_required_plugin_files_exist(self):
        for name in ("__init__.py", "main.py", "metadata.yaml", "_conf_schema.json", "requirements.txt", "LICENSE"):
            self.assertTrue((PLUGIN_DIR / name).is_file(), name)

    def test_configuration_schema_is_valid_and_contains_token(self):
        schema = json.loads((PLUGIN_DIR / "_conf_schema.json").read_text(encoding="utf-8"))
        self.assertIn("MRCN_ACCESS_TOKEN", schema)
        self.assertEqual(schema["MRCN_ACCESS_TOKEN"]["default"], "")
        self.assertTrue(schema["MRCN_ACCESS_TOKEN"]["obvious_hint"])
        self.assertEqual(schema["MRCN_DEFAULT_SEASON"]["default"], 19)
        self.assertEqual(schema["MRCN_ASSET_CACHE_DIR"]["default"], "")
        self.assertEqual(schema["MRCN_ASSET_REFRESH_DAYS"]["default"], 30)
        self.assertEqual(schema["MRCN_ASSET_MAX_CONCURRENCY"]["default"], 4)
        self.assertEqual(schema["MRCN_ASSET_TIMEOUT_SECONDS"]["default"], 10)
        self.assertTrue(schema["MRCN_META_ENABLED"]["default"])
        self.assertEqual(schema["MRCN_RIVALSMETA_BASE_URL"]["default"], "https://rivalsmeta.com")
        self.assertEqual(schema["MRCN_META_TIMEOUT_SECONDS"]["default"], 10)
        self.assertEqual(schema["MRCN_META_CACHE_SECONDS"]["default"], 600)
        self.assertEqual(schema["MRCN_META_STALE_SECONDS"]["default"], 86400)
        self.assertNotIn("MRCN_CARD_ENABLED", schema)
        self.assertNotIn("MRCN_CARD_THEME", schema)
        self.assertNotIn("MRCN_CARD_FALLBACK_TEXT", schema)
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
        self.assertIn("version: 0.14.2", metadata)
        self.assertIn('"0.14.2"', main)
        self.assertIn('astrbot_version: ">=4.19.6"', metadata)
        self.assertIn("qq_official", metadata)
        self.assertIn("qq_official_webhook", metadata)
        readme = (PLUGIN_DIR / "README.md").read_text(encoding="utf-8")
        self.assertIn("信息图片", readme)
        self.assertIn("卡片按钮", readme)

    def test_single_core_source_is_present(self):
        for relative in (
            "models.py", "hero_names.py", "game_metadata.py", "datasource/base.py",
            "datasource/cn.py", "services/rivals.py", "storage/bindings.py",
        ):
            self.assertTrue((PLUGIN_DIR / "marvel_rivals_bot" / relative).is_file(), relative)
        legacy_root = PLUGIN_DIR / "astrbot_plugin_marvel_rivals"
        self.assertFalse(
            any(path.is_file() for path in legacy_root.rglob("*")) if legacy_root.exists() else False
        )

    def test_html_player_card_has_been_removed(self):
        self.assertFalse((PLUGIN_DIR / "templates" / "player_card.html").exists())
        self.assertFalse((PLUGIN_DIR / "marvel_rivals_bot" / "presenters" / "cards.py").exists())

    def test_help_documents_commands_and_season_codes(self):
        main = (PLUGIN_DIR / "main.py").read_text(encoding="utf-8")
        for text in (
            "/帮助", "/绑定账号", "/解绑账号", "/战绩", "/最近对局", "/英雄数据", "/对局详情", "/卡片测试",
            "/英雄环境", "/英雄排行", "/英雄统计", "S0", "S9.5", "英雄名称",
        ):
            self.assertIn(text, main)
        self.assertIn("/帮助\n显示完整指令帮助\n\n/绑定账号 <UID>\n", main)

    def test_new_commands_and_legacy_aliases_are_registered(self):
        main = (PLUGIN_DIR / "main.py").read_text(encoding="utf-8")
        for command in (
            "帮助", "漫威帮助", "绑定账号", "绑定漫威", "解绑账号", "解绑漫威",
            "最近对局", "最近", "英雄数据", "英雄", "对局详情", "对局", "英雄环境", "英雄排行", "英雄统计",
        ):
            self.assertIn(f'@filter.command("{command}")', main)
        self.assertNotIn('@filter.command("help")', main)

    def test_httpx_dependency_is_declared(self):
        requirements = (PLUGIN_DIR / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("httpx", requirements)

    def test_release_metadata_uses_repository_root(self):
        metadata = (PLUGIN_DIR / "metadata.yaml").read_text(encoding="utf-8")
        self.assertIn("repo: https://github.com/Moh114514/MarvelRivalsCNPlugin", metadata)
        self.assertNotIn("astrbot_plugin_marvel_rivals/", metadata)

    def test_release_validator_accepts_current_source(self):
        self.assertEqual(validate_source(PLUGIN_DIR), "0.14.2")

    def test_release_zip_imports_as_installed_plugin_package(self):
        temp_dir = PLUGIN_DIR / ".test-release-package"
        temp_dir.mkdir()
        try:
            archive_path = Path(temp_dir) / "plugin.zip"
            from tools.release import build_archive

            build_archive(archive_path, PLUGIN_DIR)
            install_root = Path(temp_dir) / "plugins"
            plugin_root = install_root / "astrbot_plugin_marvel_rivals"
            plugin_root.mkdir(parents=True)
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(plugin_root)
            probe = (
                "import astrbot_plugin_marvel_rivals.main as plugin; "
                "assert plugin.MarvelRivalsPlugin.__name__ == 'MarvelRivalsPlugin'"
            )
            result = subprocess.run(
                [sys.executable, "-c", probe],
                cwd=install_root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        finally:
            for path in sorted(temp_dir.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            temp_dir.rmdir()

    def test_release_zip_contains_only_declared_runtime_files(self):
        temp_dir = PLUGIN_DIR / ".test-release-manifest"
        temp_dir.mkdir()
        try:
            archive_path = Path(temp_dir) / "plugin.zip"
            from tools.release import build_archive

            build_archive(archive_path, PLUGIN_DIR)
            with zipfile.ZipFile(archive_path) as archive:
                names = set(archive.namelist())
            self.assertIn("LICENSE", names)
            self.assertNotIn("tests", {Path(name).parts[0] for name in names})
            self.assertTrue(all(Path(name).suffix in {"", ".py", ".json", ".yaml", ".txt", ".md", ".png"} for name in names))
            self.assertIn("rendering/assets/part-news-bg_ac16ec22.png", names)
            self.assertIn("rendering/assets/list-l_8a1441f6.png", names)
        finally:
            for path in sorted(temp_dir.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            temp_dir.rmdir()


if __name__ == "__main__":
    unittest.main()
