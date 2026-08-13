# Changelog

本项目遵循 SemVer。`0.x` 版本仍可能调整 API 适配和配置，但会尽量保持已有命令与绑定数据兼容。

## [0.12.4] - 2026-08-13

### Added

- 将仓库根目录确定为 AstrBot 插件根目录。
- 增加统一的发布包校验与 ZIP 构建脚本。
- 增加 GitHub Actions CI 与 tag Release 流程。
- 为绑定数据库增加 schema version 基础设施。

### Changed

- 统一 `metadata.yaml`、`main.py`、`pyproject.toml` 和发布 tag 的版本来源。
- 发布包只包含插件运行所需文件，不包含测试、抓包、凭据和开发工具。
- 插件身份继续使用 `MR-bot/astrbot_plugin_marvel_rivals`。

### Fixed

- 消除开发核心与 AstrBot 插件核心的双份维护路径。
- 修正根目录插件加载时的绝对导入路径。

### Deprecated

- 不再支持从仓库内的 `astrbot_plugin_marvel_rivals/` 子目录安装；请使用仓库根目录或 GitHub Release ZIP。

### Breaking Changes

- 本次仅改变源码仓库布局，不改变 AstrBot 数据目录 `data/plugin_data/astrbot_plugin_marvel_rivals/`，已有绑定数据无需迁移。
