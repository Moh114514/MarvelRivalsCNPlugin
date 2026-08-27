# Marvel Rivals CN AstrBot Plugin

漫威争锋国服战绩查询插件，面向 AstrBot，支持 QQ Official、NapCat/OneBot 和其他兼容的 QQ 适配器。

当前稳定版本：`1.3.9`

## Player Rating V2

个人英雄分析已接入可解释的 Rating V2 与英雄战术原型层。V2 将结果拆为 Outcome、Combat、Consistency、Experience、Confidence、Performance、Mastery 和 Leave-one-out Specialization；Combat 按英雄的战术原型与同类英雄稳健基线比较，缺失指标不会被当作零分。快速模式只参与经验与辅助证据，不直接参与 HeroPerformance。

`MRCN_RATING_VERSION` 支持 `v1`、`shadow`、`v2`，默认 `shadow`：会计算并缓存 V2，同时保持现有用户输出和候选规则；切换为 `v2` 后，绝活、绝症和英雄池会使用 V2 的 Mastery、Performance、Confidence、Specialization 与战术标签。评分不使用 TrueSkill、机器学习、未验证动态字段或强制额外请求；未知/不可观测维度显示为不可用。统计仍是非官方、基于第三方已追踪玩家样本的分析结果。

Specialization 的证据门槛可通过 `MRCN_RATING_SPECIALIZATION_MIN_CONFIDENCE` 与 `MRCN_RATING_SPECIALIZATION_MIN_EXPERIENCE` 调整；缺少 Outcome、Combat、Consistency 可观测信号时始终保持不可用。Combat 会保留原有基线 fallback，并记录基线粒度、peer 数量及原始/收缩维度分数供校准使用。

## 1.3.9 Rating V2 Calibration Round 1

- Career Scope 的“潜力绝活”最低 Mastery 调整为 68.0；Specialization 与 Confidence 门槛保持不变。
- Rating 分类缓存 schema 已升级，避免复用旧分类结果。

## 1.3.7 对局交互与信息布局修复

- `/对局详情` 与 `/对局` 统一为一个 alias handler，保留按用户和群组隔离的 10 分钟选择会话。
- 单局详情改为纵向双队 scoreboard，实际 K/D/A 为主指标，伤害、治疗、承伤的每 10 分钟值作为辅助数据。
- `/我的绝活` 改为英雄状态 badge 与 3×2 指标布局，并在中等宽度提前切换为上下结构。
- 对局命令入口、选择解析、数据请求和图片渲染排队/执行阶段增加诊断日志。

## 1.3.6 时间窗口对局选择

- `/战绩回顾` 和 `/每日战绩` 的图片结果后会提供与 `/最近对局` 一致的具体对局选择按钮；非 QQ Official 平台可回复 `/对局 1` 到 `/对局 N`。
- 最近对局、战绩回顾和每日战绩的编号选择会话默认保留 10 分钟；窗口超过 25 场时图片自动分页，卡片展示前 25 场，其余场次继续使用编号查询。
- 时间窗口英雄表现补充每 10 分钟治疗和承伤，并在旧接口缺少 `playTime` 时继续明确显示兼容场均口径。

## 1.3.5 时间窗口每 10 分钟统一口径

- `/战绩回顾`、`/每日战绩`、`/最近对局` 和 `/对局详情` 在接口返回玩家实际 `playTime` 时，击败、死亡、助攻、最后一击、伤害、治疗和承伤统一按每 10 分钟展示；原始总量和游戏时间仍保留用于核对。
- 职责与英雄统计优先读取详情中的 `matchPlayer.playerHeroes[]`，使用每个英雄的 `playTime` 分账；主英雄按使用时长最长的英雄确定，多英雄对局会标注切换数量。
- `/查询`、`/我的英雄`、英雄池和绝活分析继续使用 Career/HeroCareer 生涯/赛季数据；其中有可用游戏时长时，详细战斗指标同样按每 10 分钟展示。
- 新增 `MRCN_MATCH_DETAIL_CACHE_SECONDS`，默认 `86400` 秒；旧接口缺少玩家实际时长时会保留场均回退并标记为兼容数据。

## 1.3.4 通用时间窗口输入与职责统计

- 日期-only 时间范围支持 `8月20日-8月21日`、`8月20日 8月21日` 和 `8月20日到8月21日`，并包含结束日期。
- 新增正式入口 `/战绩回顾`；`/每日战绩` 和 `/今日战绩` 是整日时间窗口的快捷入口。
- 支持今天、昨天、明确日期、日内时间段、跨日范围、最近 1/3/6/12/24 小时和本周，统一使用北京时间 `[start, end)` 查询，单次最多 7 天。
- 时间范围查询不要求用户输入赛季；Summary 会先执行服务端时间过滤，再按 100 条分页，详情按每批 10 场加载并复用 `matchUid` 缓存。
- 统计和对局列表统一使用 `MatchTimeWindow`、`MatchWindowReport`、`MatchRecord`；超过 25 场时自动发送多张图片，`/对局 N` 可查看当前列表中的任意一场。
- 战绩聚合新增 `RoleWindowStats`：捍卫者、决斗家、策略家分别保存总量和样本数，伤害/治疗/承伤的场均值使用各自职责分母；总览只强调跨职责可相加的总量，英雄表现按职责分组展示全部已使用英雄。
- 旧版职责统计按单局 `matchPlayer.curHeroId` 回退；新版优先使用详情 `playerHeroes[].playTime`，缺少该字段时才保留旧口径。
- 交互 Session 按用户和群组隔离，默认保留 10 分钟；新的最近对局或战绩回顾列表会覆盖旧列表。

## 1.3.2 通用时间窗口基础

- 新增正式入口 `/战绩回顾`；`/每日战绩` 和 `/今日战绩` 是整日时间窗口的快捷入口。
- 支持今天、昨天、明确日期、日内时间段、跨日范围、最近 1/3/6/12/24 小时和本周，统一使用北京时间 `[start, end)` 查询，单次最多 7 天。
- 时间范围查询不要求用户输入赛季；Summary 会先执行服务端时间过滤，再按 100 条分页，详情按每批 10 场加载并复用 `matchUid` 缓存。
- 统计和对局列表统一使用 `MatchTimeWindow`、`MatchWindowReport`、`MatchRecord`；超过 25 场时自动发送多张图片，`/对局 N` 可查看当前列表中的任意一场。
- 交互 Session 按用户和群组隔离，默认保留 10 分钟；新的最近对局或战绩回顾列表会覆盖旧列表。

## 1.3.1 每日战绩

- `/每日战绩` 作为通用时间窗口的整日快捷入口，支持今天、昨天、明确日期和 UID；`/今日战绩` 是今天的兼容别名。
- 每日战绩使用北京时间半开区间向国服 Summary 接口查询，支持分页、每 10 场一批详情、详情缓存和同 key SingleFlight，不通过最近对局历史扫描兜底。
- 图片展示总计、快速/竞技/其他模式、K/D/A、每10分钟指标和 Top 5 英雄；旧接口没有玩家实际时长时兼容显示场均值，`gameModeId=4` 保留为其他模式。

## 1.3.0 个人英雄分析系统

- /我的英雄、/我的英雄池、/我的绝活、/我的绝症统一使用 PlayerCareerAnalysisService；英雄池指标从同一份分析结果本地派生，不再重复请求旧的单赛季英雄池接口。
- 四条命令都支持生涯或指定赛季，赛季 UI 统一显示 S9、S9.5 等规范名称。使用量门槛与评分分离：总场次至少 10，或竞技至少 5，或快速至少 20 才进入分析候选；Performance 在 -10 到 +10 之间属于中性区。
- Meta 未启用时仍加载个人生涯/赛季、快速、竞技和个人基准数据，Meta 字段显示为不可用并明确提示，不回退到旧的默认当前赛季口径。
- `/我的英雄`、`/我的英雄池`、`/我的绝活`、`/我的绝症` 统一使用 `PlayerCareerAnalysisService`，共享同一份完整英雄分析结果。
- 四条命令都支持生涯或指定赛季；UID 与赛季参数顺序不限。分析同时保留快速、竞技的完整模式统计，并使用统一的 -100 到 +100 Performance Index。

## 1.2.0 命令体验与 OneBot 适配

- 正式入口为 `/我的英雄`，`/英雄数据` 和 `/英雄` 继续兼容；英雄支持常用别称，职责显示为捍卫者、决斗家、策略家，Meta 职责输入支持 `T位`、`C位`、`奶位`。
- `/英雄排行` 支持职责筛选、分职责榜、前 N、指定区间和最后 N，严格按“筛选职责 → 排序 → 范围截取”执行。
- 个人英雄数据增加最后一击、每10分钟伤害、每10分钟治疗和每10分钟承伤，保留 `MVP / SVP`；无场次、时长或缺失总量显示 `—`。
- 同一玩家/英雄/最近对局/对局详情请求支持 SingleFlight 合并；外部请求和 HTML→PNG 渲染分别限流，渲染失败最多重试一次并返回短错误提示。
- OneBot 群聊图片结果通过 AstrBot 消息链恢复 @；最近对局和战绩回顾都保存数字选择会话，支持回复 `/对局 N`。QQ Official 最近对局原生按钮保持不变。

## 1.1.6 性能优化

- 复用国服与全局 Meta HTTP 连接池，插件停止或重载时统一释放连接。
- `/查询` 的核心请求并发执行，Top 10 HeroCareer 改为 Quick/Competitive 各一次批量请求。
- `/英雄数据` 的快速与竞技数据并发请求；批量接口失败时保留原有的单英雄降级路径。

## 1.1.5 功能概览

- 个人战绩支持快速、竞技、总计三种统计口径；`/查询` 为正式入口，`/战绩` 保留为兼容别名。
- Player × Meta 支持 `/我的环境`、`/我的英雄池`、跨赛季 `/我的绝活` 和 `/我的绝症`，可将绑定账号或显式 UID 的国服数据与同段位 RivalsMeta 环境对比。
- `/我的绝活` 默认展示 Top 5 个长期专精候选；`/我的绝症` 独立展示最多 Top 10 个高使用量相对弱势英雄。
- 全局 Meta 支持排行榜、单英雄统计、九段位分布、双英雄对比，以及跨赛季趋势和历史洞察。
- `/英雄趋势`、`/版本变化`、`/版本黑马`、`/冷门强者`、`/热门低胜率`、`/分段怪物` 使用按赛季缓存和透明规则，数据不可用时保留明确的暂无数据或 stale 状态。
- 查询结果优先生成统一视觉 PNG；QQ Official 仅为 `/最近对局` 保留单局选择按钮，图片渲染或富消息失败时回退为图片/普通文本。
- 运行时图片使用独立 Asset Cache，缓存保存在 AstrBot 数据目录，不写入源码目录，也不进入发布 ZIP。

国服数据接口来自官方微信小程序请求。接口不是公开稳定 API，接口地址、请求头、请求体和短期 Token 都可能变化，因此本插件把这些内容放在配置中，并提供 `mitmproxy` 采集工具辅助更新配置。

## 快速开始

1. 将仓库根目录作为 AstrBot 插件目录安装。仓库根目录已经直接包含 `main.py`、`metadata.yaml`、`_conf_schema.json` 和 `requirements.txt`，不需要再套一层 `astrbot_plugin_marvel_rivals/`。
2. 按下方“抓包并获取 Token”操作，得到当前可用的接口配置。
3. 在 AstrBot WebUI 的插件配置中填写 `MRCN_ACCESS_TOKEN`，并核对接口地址、请求头、路径和请求体模板。
4. 重载插件后执行 `/帮助` 和 `/查询 <UID>` 验证。

Token 是微信小程序会话中的临时凭据，不是玩家 UID。Token 决定请求使用哪个小程序会话，命令中的 UID 决定查询哪个玩家；查询其他玩家还要求对方在小程序中开放战绩查询权限。

## 抓包并获取 Token

这是推荐的配置获取方式。以下命令均在仓库根目录执行，Windows PowerShell 示例适用。

### 1. 安装并启动采集器

`mitmproxy` 是抓包工具，不是插件运行依赖：

```powershell
python -m pip install mitmproxy
mitmdump -s tools/mitm_capture.py --set capture_dir=captures
```

`mitmdump` 默认监听 `127.0.0.1:8080`。让微信桌面端使用系统代理 `127.0.0.1:8080`；如果使用手机微信，则将 Wi-Fi 代理指向运行 mitmproxy 的电脑 IP 和 `8080` 端口。

首次使用时，在被抓包设备上访问 `http://mitm.it`，按提示安装 mitmproxy CA 证书。HTTPS 无法解密时，通常是代理没有生效或证书没有安装/信任。抓包完成后可以关闭系统代理并移除临时证书信任。

### 2. 在微信小程序中制造请求

打开“漫威争锋”国服小程序，依次执行尽可能多的操作：

- 查看玩家战绩；
- 打开英雄详情；
- 查看最近对局；
- 打开一场对局详情。

采集器会识别 `s3.game.163.com` 下的已知接口，以及路径中包含 `match`、`battle`、`history`、`record` 或 `recent` 的请求。完成后回到 mitmdump 窗口按 `Ctrl+C` 停止。

默认输出：

```text
captures/flows.json       # 脱敏后的请求/响应样本
captures/mrcn_config.json # 根据抓包结果生成的配置草稿
```

### 3. 获取可用 Token

默认模式会脱敏 `Cookie`、`Authorization`、`access_token`、其他 Token 类请求头和签名，因此默认生成的文件适合分析接口，但不能直接用于鉴权。

如果需要进行一次本地验证，确认 `captures/` 目录只有自己可访问后，再重新抓包：

```powershell
$env:MRCN_CAPTURE_INCLUDE_SENSITIVE="1"
mitmdump -s tools/mitm_capture.py --set capture_dir=captures
```

重新打开小程序并执行一次查询，然后停止采集器。此时可以在本机的 `captures/flows.json` 或 `captures/mrcn_config.json` 中查看真实请求头，找到小程序请求里的 `access_token` 值。

建议先用默认脱敏模式确认接口，再只为本地 PoC 临时开启敏感信息采集。使用完成后清除环境变量：

```powershell
Remove-Item Env:MRCN_CAPTURE_INCLUDE_SENSITIVE -ErrorAction SilentlyContinue
```

不要把包含 Token 的抓包文件、截图、日志或 `.env.capture` 上传到 GitHub、Issue、群聊或其他共享位置。Token 过期后返回 401 或“Token 失效”时，需要重新抓包获取。

### 4. 应用配置草稿

可以先把采集结果转换为 CLI 使用的本地配置文件：

```powershell
python tools/apply_capture.py captures/mrcn_config.json --output .env.capture
python -m marvel_rivals_bot.cli --env-file .env.capture config-check
```

`apply_capture.py` 生成的是配置草稿，不代表所有接口模板都已经确认。请以 `captures/flows.json` 中每个接口的实际请求为准，特别是 `MRCN_*_BODY_TEMPLATE`。不同接口的请求体通常不同，不要把某一个接口的请求体盲目复制给所有接口。

在 AstrBot WebUI 中建议按以下方式填写：

```text
MRCN_API_BASE_URL=抓包得到的接口前缀
MRCN_HEADERS_JSON={"User-Agent":"Mozilla/5.0","Content-Type":"application/json"}
MRCN_ACCESS_TOKEN=抓到的 access_token 值
```

`MRCN_ACCESS_TOKEN` 会被插件自动作为 `access_token` 请求头注入，并覆盖 `MRCN_HEADERS_JSON` 中同名的旧值。不要把 Token 同时保存在两处。

如果抓到的鉴权头不是 `access_token`，例如是 `Authorization: Bearer ...`，则不要填写 `MRCN_ACCESS_TOKEN`，而应在 `MRCN_HEADERS_JSON` 中保留完整的鉴权头：

```text
MRCN_HEADERS_JSON={"Authorization":"Bearer <token>","Content-Type":"application/json"}
MRCN_ACCESS_TOKEN=
```

### 5. 请求体和路径配置

默认接口路径和模板已经内置；只有抓包证据与默认值不一致时才需要修改。配置名称与抓包中的接口对应：

| 配置 | 用途 | 常用占位符 |
| --- | --- | --- |
| `MRCN_API_BASE_URL` | 接口前缀，例如 `https://s3.game.163.com/35a06fa941672d97` | 无 |
| `MRCN_HEADERS_JSON` | 非敏感请求头 JSON | 无 |
| `MRCN_ACCESS_TOKEN` | `access_token` 请求头的值 | 无 |
| `MRCN_DEFAULT_SEASON` | 未指定赛季时使用的接口赛季代码 | 无 |
| `MRCN_ROLE_PATH` | 根据 UID 查询角色的 GET 接口 | 无 |
| `MRCN_DATA_BODY_TEMPLATE` | `loadData` 请求体 | `{player_uid}` |
| `MRCN_SUMMARY_BODY_TEMPLATE` | 综合/最近对局请求体 | `{season}`、`{player_uid}` |
| `MRCN_CAREER_BODY_TEMPLATE` | 快速 + 竞技总计生涯数据请求体 | `{season}`、`{player_uid}` |
| `MRCN_CAREER_QUICK_BODY_TEMPLATE` | 快速模式生涯数据请求体 | `{season}`、`{player_uid}` |
| `MRCN_CAREER_RANKED_BODY_TEMPLATE` | 竞技模式生涯数据请求体 | `{season}`、`{player_uid}` |
| `MRCN_SORT_HERO_BODY_TEMPLATE` | 常用英雄请求体 | `{season}`、`{player_uid}` |
| `MRCN_HERO_BODY_TEMPLATE` | 快速 + 竞技总计英雄请求体 | `{hero_ids}`、`{season}`、`{player_uid}` |
| `MRCN_HERO_QUICK_BODY_TEMPLATE` | 快速模式英雄请求体 | `{hero_ids}`、`{season}`、`{player_uid}` |
| `MRCN_HERO_RANKED_BODY_TEMPLATE` | 竞技模式英雄请求体 | `{hero_ids}`、`{season}`、`{player_uid}` |
| `MRCN_SUMMARY_DETAIL_BODY_TEMPLATE` | 对局详情请求体 | `{match_uids}` |

`/战绩回顾` 的时间窗口请求仍复用 `MRCN_SUMMARY_BODY_TEMPLATE`，但由数据源动态写入 `page`、`pageSize`、模式集合和可选的 `matchTimeStamp`；不指定赛季时会移除模板中的 `matchSeason` 条件，以支持跨赛季时间查询。

例如抓包确认 `loadData` 使用 `aid` 和 `zoneId`，只修改对应模板：

```text
MRCN_DATA_BODY_TEMPLATE={"aid":{player_uid},"zoneId":16001}
```

`MRCN_REQUEST_BODY_TEMPLATE` 是旧配置兼容项。新配置优先使用上表中的具体 `MRCN_*_BODY_TEMPLATE`，避免一个通用模板覆盖多个接口。请求体必须是合法 JSON；占位符应保留在 JSON 中，插件会在实际请求时替换。

## 使用命令

### AstrBot 命令

```text
/帮助
/绑定账号 <UID>
/解绑账号
/查询 [UID] [赛季]
/最近对局 [UID] [赛季]
/战绩回顾 [时间范围] [UID]
/每日战绩 [日期] [UID]
/我的英雄 <英雄名称> [UID] [赛季]
/我的环境 [UID] [赛季]
/我的英雄池 [UID] [赛季]
/我的绝活 [UID] [赛季]
/我的绝症 [UID] [赛季]
/英雄环境 [段位] [赛季]
/英雄排行 <胜率|选取率|Ban率|场次> [职责] [段位] [赛季] [范围]
/英雄统计 <英雄名称> [段位] [赛季]
/英雄分段 <英雄名称> [赛季]
/英雄对比 <英雄1> <英雄2> [段位] [赛季]
/英雄趋势 <英雄名称> [段位] [赛季...]
/版本变化 <旧赛季> <新赛季> [段位]
/版本黑马 [段位] [旧赛季] [新赛季]
/冷门强者 [段位] [赛季]
/热门低胜率 [段位] [赛季]
/分段怪物 [赛季]
/对局详情 <matchUid|N>
/对局 <N>
/卡片测试
```

已绑定账号后，`UID` 可以省略。职责可写捍卫者/先锋/捍卫/T位/坦克、决斗家/决斗/C位/DPS、策略家/战略/奶位/辅助；范围可写前 10、Top10、1-10、11-20、最后 10。英雄别称例如 `杰夫`、`鲨鱼`、`恐龙` 会归一化为完整英雄名；裸输入 `死侍` 会提示选择职责版本。

例如：

```text
/绑定账号 1287101468
/查询
/战绩回顾
/战绩回顾 昨天
/战绩回顾 8月15日
/战绩回顾 今天 14:00-18:00
/战绩回顾 8月20日-8月21日
/战绩回顾 8月20日 8月21日
/战绩回顾 8月20日到8月21日
/战绩回顾 最近6小时
/战绩回顾 2026-08-15 20:00 2026-08-16 02:00
/每日战绩
/每日战绩 昨天
/每日战绩 2026-08-15 195963667
/英雄数据 蜘蛛侠 S9.5
/我的英雄 杰夫 S9.5
/英雄环境 大师 S9.5
/英雄排行 Ban率 天神 S9.5 前10
/英雄排行 胜率 分职责 前5
/英雄统计 曼蒂斯 大师 S9.5
/英雄分段 蜘蛛侠 S9.5
/英雄对比 蜘蛛侠 黑豹 铂金 S9.5
/英雄趋势 蜘蛛侠 大师 S8 S8.5 S9 S9.5
/我的环境 1287101468 S9.5
/我的英雄池 1287101468 S9.5
/我的绝活 uid=1287101468 S9.5
/我的绝症 uid=1287101468 S9.5
/版本变化 铂金 S9 S9.5
/版本黑马 大师 S9 S9.5
/冷门强者 大师 S9.5
/热门低胜率 大师 S9.5
/分段怪物 S9.5
/最近对局 S9下半赛季
```

`/战绩回顾` 支持 `今天`、`昨天`、`YYYY-MM-DD`、`YYYY/MM/DD`、`MM-DD`、`M月D日`、日期范围 `8月20日-8月21日`、`8月20日 8月21日`、`8月20日到8月21日`、日内时间段 `今天 14:00-18:00`、跨日期带时间 `开始日期 开始时间 结束日期 结束时间`（例如 `2026-08-15 20:00 2026-08-16 02:00`）、`最近6小时` 和 `本周`；日期-only 范围包含结束日期，统一转换为北京时间半开区间查询。未指定时间范围时使用今天，未指定 UID 时使用绑定账号。未来尚未开始的范围、起点不早于终点的范围和超过 7 天的范围会被拒绝。时间范围查询无需指定赛季。`/每日战绩` 只接受日期和 UID，是整日时间窗口快捷入口；空结果会正常显示“暂无对局记录”。

支持的赛季写法：`S0`、`S9`、`S9.5`、`S9上半赛季`、`S9下半赛季`，不区分 `s/S` 大小写。Meta 段位支持全段位、单段位，以及 `钻石+`、`大师+`、`天神+`、`永恒+`；输出统一使用国服段位名称。`/英雄环境` 只接受段位和赛季，展示胜率、选取率、Ban率三个 TOP5 总览；`/英雄排行` 必须且只能指定一个排序指标，且不接受英雄名称；`/英雄统计` 接受英雄名称、段位和赛季，不接受排序指标；`/英雄分段` 展示该英雄在九个 Meta 大段位的 WR、选取率和 Ban率，不接受段位筛选；`/英雄对比` 接受两个不同的中文英雄名称、段位和赛季，不接受排序指标。`/英雄趋势` 支持多个赛季，未指定时比较最近四个已知赛季，逐赛季展示胜率、选取率、Ban率、样本场次及相对上一赛季的变化，单个赛季不可用时保留暂无数据点；`/版本变化` 按两个赛季快照比较，必须按旧赛季到新赛季填写，不代表真实补丁版本；`/版本黑马` 使用当前胜率不低于环境中位数、较上一赛季提升至少 2.0pp、样本至少 100 场的透明规则，也必须按旧赛季到新赛季填写；`/冷门强者` 使用胜率不低于中位数、选取率低于中位数、Ban率低于中位数及最低 100 场样本的透明规则，青铜和白银没有 Ban 位，因此不引入 Ban率；其他段位 Ban 数据不足时会明确提示，`/热门陷阱` 为 `/热门低胜率` 的兼容别名；`/分段怪物` 按九个大段位的游戏顺序列出所有满足最低样本且相对自身全段位胜率高至少 2.0pp 的英雄，不做跨段位排名。`/我的绝活` 默认展示 Top 5，跨 S0 到当前赛季扫描有记录的英雄；有效赛季按竞技模式出场即计入，长期稳定性只在有同期 Meta 时计算，并按竞技场次加权。`/我的绝症` 默认展示 Top 10，使用 Sickness Score 连续排序；候选须满足总场次至少 10、或竞技至少 5、或快速至少 20，且 Performance ≤ -10、Sickness Score > 0；个人基准采用排除当前英雄的留一法并进行小样本收缩，与 `/我的绝活` 从同一个 Performance 轴派生。所有历史洞察仍来自第三方已追踪 Meta 样本。英雄命令使用中文英雄名称，不使用数字英雄 ID。`/帮助` 是本插件帮助，AstrBot 内置 `/help` 也会根据命令说明列出功能。

旧命令仍保留兼容：`/漫威帮助`、`/绑定漫威`、`/解绑漫威`、`/最近`、`/英雄`、`/对局`。

全局英雄环境数据来自第三方 RivalsMeta，不代表网易或 Marvel 官方统计。Meta 数据按赛季缓存到 AstrBot 的 `data/plugin_data/astrbot_plugin_marvel_rivals/meta/`；上游暂时不可用时会在有效期内展示最近缓存，并明确标记 stale 状态。英雄、段位和赛季使用统一 Game Reference；CN 细分段位会在服务边界转换为 Meta 大段位，CN 与 RivalsMeta 的赛季编号保持独立。Meta 查询默认生成统一视觉图片，渲染失败时回退文本；历史洞察同样复用每赛季缓存，不创建玩家历史数据链。皮肤、段位人口、Tier、地图/Team-Up 和玩家历史查询仍不在范围内。

QQ Official 查询和 `/帮助` 会生成统一视觉的信息图片；只有 `/最近对局` 会附带用于选择单局的卡片按钮，`/战绩回顾` 通过图片列表和 `/对局 N` 选择。其他查询不再发送无意义的 Markdown 或导航按钮；不支持富消息或发送失败时会回退为图片/普通文本。群聊中会自动 @ 命令发起者。绑定数据保存在 AstrBot 的 `data/plugin_data/astrbot_plugin_marvel_rivals/bindings.sqlite3`。

### 运行时图片缓存

英雄图片采用本地 Asset Cache：默认保存到 `data/plugin_data/astrbot_plugin_marvel_rivals/assets/`，不会写入插件源码目录，也不会进入 Release ZIP。插件启动不会同步等待图片下载；当后续接入已确认的英雄图片 URL 后，可由后台预热，查询时则优先读取本地缓存，缺失时懒加载，失败时继续使用 CSS-only 页面。

缓存由 `rendering/assets.py` 的 `AssetManager` 管理，维护 `manifest.json`，支持 URL 变化检测、30 天重新校验、ETag/Last-Modified 条件请求、最多 4 路并发预热和原子文件写入。详细边界、配置项和维护接口见 [`docs/asset-cache.md`](docs/asset-cache.md)。

## 本地验证

本地 CLI 使用 `.env.capture`，不会读取 AstrBot WebUI 中的配置：

```powershell
# 只检查配置，不发请求，也不会打印 Token
python -m marvel_rivals_bot.cli --env-file .env.capture config-check

# 执行真实请求
python -m marvel_rivals_bot.cli --env-file .env.capture player 195963667
python -m marvel_rivals_bot.cli --env-file .env.capture recent 195963667
python -m marvel_rivals_bot.cli --env-file .env.capture hero 1066 195963667
python -m marvel_rivals_bot.cli --env-file .env.capture match <matchUid>
```

CLI 的 `hero` 子命令使用数字英雄 ID，赛季使用当前 `MRCN_DEFAULT_SEASON`；赛季名称和中文英雄名称转换由 AstrBot 命令层处理。使用 `--raw-output` 可以把接口 JSON 保存到本地，使用 `--debug` 可以查看请求体和响应顶层字段，但不要把输出文件或日志分享出去：

```powershell
python -m marvel_rivals_bot.cli --env-file .env.capture --raw-output debug-responses/player.json player 195963667
```

## 常见问题

### 返回 401、Token 失效或鉴权失败

重新抓包获取 Token，确认它来自最新一次微信小程序请求；同时确认鉴权头名称。如果是 `access_token`，使用 `MRCN_ACCESS_TOKEN`；如果是 `Authorization` 等其他名称，放入 `MRCN_HEADERS_JSON`。

### 抓不到请求或 `flows.json` 为空

确认微信实际使用了 `127.0.0.1:8080`（手机使用电脑局域网 IP）、mitmproxy CA 已安装并受信任，并且在小程序中重新打开了战绩页面。只抓到了普通网页请求时，通常是代理未生效。

### SSL 证书错误

本地通过 mitmproxy 调试时，可以把 mitmproxy CA PEM 文件路径填入 `MRCN_CA_CERT`，或让本地 HTTP 客户端使用该证书。生产环境保持 `MRCN_VERIFY_SSL=true`，不要为了绕过证书错误而长期关闭 TLS 校验。

### 查询其他玩家失败

如果接口返回“不允许查看该用户的游戏数据”，请让对方在“漫威争锋小程序 → 战绩 → 设置”中打开查询权限。这不是 Token 配置错误。

### 接口返回成功但没有字段

先检查 `flows.json` 和原始响应，再按实际字段更新解析逻辑或请求模板。不要根据未知地图 ID、赛季代码或字段名进行猜测；接口变更时应保留原始响应供定位。

## 安装与开发

AstrBot 会根据 `requirements.txt` 安装运行依赖。手动开发时可以运行：

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m py_compile main.py marvel_rivals_bot\datasource\cn.py
```

构建发布包：

```powershell
python tools/release.py --check
python tools/release.py --build dist/astrbot_plugin_marvel_rivals-v<version>.zip
```

版本需要同步更新 `metadata.yaml`、`main.py` 的 `@register` 和 `pyproject.toml`。请勿提交 Token、Cookie、授权头、抓包文件、原始响应、`.env.capture`、本地数据库或代理证书。
## Player × Meta

CN 生涯、常用英雄和单英雄接口分别请求快速（`gameModeId=1`）与竞技（`gameModeId=2`）模式，统一使用 `playModeId=0`；对应请求体支持 `*_QUICK_BODY_TEMPLATE`、`*_COMPETITIVE_BODY_TEMPLATE`，旧 `*_RANKED_BODY_TEMPLATE` 仍兼容。`loadSortHero` 只用于发现/排序候选英雄，模式场次、胜场和胜率以每个英雄独立请求的 `loadHeroCareer` 为准；单个模式请求失败时保留该模式为未知，不把它当成 0。

绝活分析的 AstrBot 配置项如下，默认值已写入 `_conf_schema.json` 和 `.env.example`：

| 配置 | 默认值 | 用途 |
| --- | --- | --- |
| `MRCN_SIGNATURE_HERO_BATCH_SIZE` | `32` | 单次 HeroCareer 请求最多携带的英雄数量 |
| `MRCN_SIGNATURE_MAX_CONCURRENCY` | `4` | CN 与 Meta 请求的最大并发数 |
| `MRCN_SIGNATURE_SEASON_POLICY` | `independent` | 赛季快照口径，支持 `independent` 或 `cumulative` |
| `MRCN_SIGNATURE_RESULT_CACHE_SECONDS` | `900` | 最终个人绝活结果缓存时长 |
| `MRCN_SIGNATURE_HISTORY_CACHE_SECONDS` | `604800` | 历史赛季 HeroCareer 缓存时长 |
| `MRCN_SIGNATURE_CURRENT_CACHE_SECONDS` | `1800` | 当前赛季 HeroCareer 缓存时长 |

/我的绝活 和 /我的绝症 现在共享 PlayerCareerAnalysisService 的完整英雄分析。无赛季时分析全生涯，指定 S9、S9.5 时只分析该赛季；UID 与赛季参数顺序不限。统一的 Performance Index 范围为 -100 到 +100，由同期同段位 Meta、同赛季个人竞技留一基准、同赛季个人快速留一基准按 55% / 30% / 15% 加权，缺失信号会重新归一权重；快速模式永远不直接与 Meta 比较。个人基准先按竞技 20 场、快速 30 场先验进行收缩，原始差值仍保留用于解释。

绝活指数为 Play Index × max(Performance Index, 0) ÷ 100 × Evidence Factor，绝症指数为 Play Index × max(-Performance Index, 0) ÷ 100 × Evidence Factor。因此同一英雄不可能同时进入正向绝活和负向绝症。候选必须满足总场次至少 10、或竞技至少 5、或快速至少 20，并且 Performance 达到 ±10；Play Index 生涯 cap 为 50 场，单赛季 cap 为 20 场。

/我的绝活 按 Signature Score、Performance Index、Evidence Factor、Play Index、总场次排序，默认展示生涯 Top 5；/我的绝症按 Sickness Score、弱势表现、Evidence Factor、Play Index、总场次排序，默认展示生涯 Top 10。生涯分类才使用有效赛季和长期稳定性；单赛季只使用赛季强势、赛季表现优秀、赛季待验证、赛季中性和赛季偏弱等本赛季语义。

/我的英雄池 回答英雄池结构而不是单纯列出使用次数：展示 Top 1/Top 3 使用占比、有效英雄池宽度、按场次加权的职责覆盖、核心英雄综合表现、正向/负向使用占比和结构标签。核心英雄满足使用占比至少 5% 或 Play Index 至少 30，最多 Top 10，并按使用占比、Play Index、总场次排序。有效宽度使用 1 ÷ Σ(使用占比²)，职责占比按实际场次计算。

已绑定账号后，可使用以下命令把国服个人数据与同段位 RivalsMeta 环境结合：

```text
/我的环境 [UID] [赛季]
/我的英雄池 [UID] [赛季]
/我的绝活 [UID] [赛季]
/我的绝症 [UID] [赛季]
```

`/我的环境`、`/我的英雄池`、`/我的绝活`、`/我的绝症` 均支持显式 UID；未提供 UID 时继续使用绑定账号。`/我的英雄 <英雄>` 默认是生涯分析，`/我的英雄 <英雄> S9.5` 只分析指定赛季，并展示结论、使用量、Meta 对比、快速/竞技相对表现和完整战斗统计。绝活与绝症只是对同一份分析结果按 `SignatureScore` 或 `SicknessScore` 筛选排序。

例如：`/我的英雄 蜘蛛侠 S9.5`、`/我的绝活 uid=1287101468 S9.5`，或 `/我的绝症 S9.5 1287101468`。

个人数据口径如下：`/查询` 展示快速、竞技和两者合计；`/英雄数据` 展示总计使用量、竞技详细数据和快速摘要；`/最近对局` 保持现有快速 + 竞技 + 其他已接入队列的混合时间线，不作为英雄池或绝活的统计口径。`/战绩` 仍保留为兼容旧命令的别名，但不再作为正式帮助入口。
