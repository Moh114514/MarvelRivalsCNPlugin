# Changelog

本项目遵循 SemVer。`0.x` 版本仍可能调整 API 适配和配置，但会尽量保持已有命令与绑定数据兼容。

## [0.14.4] - 2026-08-17

- 统一普通图片为竖屏布局，`/帮助` 保留宽屏布局；统一段位输出为“铂金”，兼容识别旧称“白金”。

## [0.14.3] - 2026-08-17

- 修复全段位 Ban 率因上游缺少低段位 Ban 桶而全部显示不可用的问题；环境总览移除与选取率重复的“场次 TOP5”。
- 完成 Meta PR-C：为 `/英雄环境`、`/英雄排行`、`/英雄统计` 接入统一视觉图片页面。
- 三类 Meta 页面统一使用稳定 ViewModel 和现有 HTML→PNG 渲染链路，保留来源、更新时间和 stale 状态；渲染或发送失败时回退文本。

## [0.14.2] - 2026-08-17

- 完成 Meta PR-B：新增统一 Game Reference 层，集中维护英雄、CN 细分段位、Meta 段位和 provider 独立赛季身份。
- 建立 CN 细分段位到 Meta 大段位的显式转换，保留 `hero_names.py`、`game_metadata.py`、`meta.ranks`、`services.rivals` 等旧导入入口兼容。

## [0.14.1] - 2026-08-17

- 完成 Meta PR-A：收紧命令职责和参数解析，修复重复参数、Ban 数据完整性、非负 schema 校验及用户/数据源错误边界。
- 增加 Meta 请求、缓存状态、stale 回退和缓存写入失败的简洁日志，并补齐对应测试。

## [0.14.0] - 2026-08-14

- 新增独立 Meta 数据域，接入 RivalsMeta 英雄环境数据、段位筛选、复合段位、All Ranks 和文本统计。
- 新增 `/英雄环境`、`/英雄排行`、`/英雄统计`，支持胜率、选取率、Ban率、场次排序及赛季/段位参数。
- 明确 Meta 命令参数职责：环境和统计不接受排序指标，排行必须且只能指定一个排序指标且不接受英雄名称。
- 新增 Meta 内存缓存、磁盘缓存和上游失败时的 stale fallback；CI 使用 MockTransport，不访问第三方网络。
- 当前阶段不包含皮肤图片、段位人口、Tier、地图/Team-Up 或 Meta 图片渲染。

## [0.13.3] - 2026-08-14

- 新增运行时 `AssetManager` 图片缓存基础设施：支持 manifest、懒加载、可选预热、条件校验、并发限制、原子写入和 Data URI。
- 图片缓存默认保存到 AstrBot `data/plugin_data/astrbot_plugin_marvel_rivals/assets/`，初始化和预热失败不会阻塞插件启动，发布包不包含运行时缓存。
- 同步 README、Asset Cache 设计文档、配置 schema 和 `.env.example`。

## [0.13.2] - 2026-08-14

- 统一有序双列列表的编号方向：第一列从上到下显示 01～05，第二列显示 06～10，覆盖常用英雄和最近对局。

## [0.13.1] - 2026-08-14

- `/帮助` 改为使用统一视觉主题生成图片；非 QQ Official 平台发送图片，失败时回退为帮助文本。

## [0.13.0] - 2026-08-14

- 完成 PR3 图片优先输出清理。
- `/战绩`、`/查询`、`/英雄数据` 和 `/对局详情` 在 QQ Official 中改为直接发送单张图片。
- 保留 `/最近对局` 的图片与第 1～10 场对局选择按钮；移除其他查询的无意义卡片导航。
- 新增语义化 `QQOfficialCardSender.send_image()` 图片发送接口。
- 修正图片视觉系统：采用紫/黄/米白高对比编排、主体 nameplate 和条带式英雄列表，降低 Cyan、网格、水印和柔和 Dashboard 阴影的存在感。
- 根据视觉复核进一步收敛页面：使用安静的浅灰紫背景与边缘黄线，将段位/积分提升为高对比元数据带，指标合并为浅色信息带，英雄和对局列表统一为浅色行。
- 微调视觉基准：背景改为冷蓝灰色阶，虚影改为低对比放射型尖锐面片，放大核心指标数字并提升英雄明细可读性，同时略微强化段位权重。
- 接入官方 `part-news-bg` 与 `list-l` 边缘素材，并将 UID 元数据调整为更宽的单行字段。

## [0.12.5] - 2026-08-14

### Added

- 补充从微信小程序抓包获取 Token、接口配置和本地验证的完整说明。

### Changed

- 重写 README 的快速开始、AstrBot 命令、请求体模板和常见问题章节。
- 明确区分脱敏抓包、临时敏感信息采集、`MRCN_ACCESS_TOKEN` 和其他鉴权请求头的配置方式。

### Fixed

- 修正 README 中旧命令和不适用 CLI 参数示例，避免按文档操作时使用错误命令。

### Compatibility

- 本版本仅更新文档和版本元数据，不改变运行时命令、配置键、API 请求逻辑或绑定数据库；可直接覆盖升级。

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
