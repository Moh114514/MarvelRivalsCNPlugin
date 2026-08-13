# Marvel Rivals CN AstrBot Plugin

这是一个面向 AstrBot 的漫威争锋国服战绩查询插件，支持 QQ Official 与 NapCat/OneBot。国服接口来自官方微信小程序抓包，目前已知接口前缀和接口路径，但请求体、认证头和最近比赛接口仍需以抓包结果为准，因此没有把临时 Cookie 或 Token 提交到代码库。

## 当前命令

```text
/漫威帮助
/绑定漫威 <UID>
/解绑漫威
/战绩 [UID] [赛季名称]
/查询 [UID] [赛季名称]
/最近 [UID] [赛季名称]
/英雄 <英雄名称> [UID] [赛季名称]
/对局 <matchUid>
/卡片测试
/同步漫威菜单（仅管理员）
/查看漫威菜单（仅管理员）
```

AstrBot 内置 `/help` 会根据各命令的说明列出可用功能，`/漫威帮助` 会显示本插件完整的参数说明与示例。`/战绩` 和 `/查询` 会调用 `loadData`、`loadSummary`、`loadCareer`、`loadSortHero`，并批量调用 `loadHeroCareer` 补全常用英雄的出场、胜场和击败。默认查询 `MRCN_DEFAULT_SEASON`，也可以通过赛季名称查询历史赛季，例如 `/战绩 1287101468 S9上半赛季`。

QQ Official 上的 `/战绩` 和 `/英雄` 会输出原生 Markdown + 消息按钮；`/最近` 与 `/对局` 会由 AstrBot 的 HTML 渲染服务生成高密度信息图片，并在图片下方保留原生消息按钮，可从最近十场直接打开任意单局详情。非 QQ Official 平台仍可查看图片，图片渲染失败时自动回退原有文本且不会重复请求国服接口。`/卡片测试` 可单独验证账号的 Markdown、指令按钮和链接按钮权限。插件不额外依赖 Pillow 或自带浏览器。

QQ 单聊快捷菜单包含“战绩、最近、英雄、账号、更多”五个一级入口，其中“账号”和“更多”为折叠菜单。先在 AstrBot 插件配置中填写 `QQ_BOT_APP_ID` 与 `QQ_BOT_CLIENT_SECRET`，再由管理员执行 `/同步漫威菜单`。该操作调用 QQ 官方 `PUT /v2/menu` 并会完整覆盖机器人已有的全局单聊菜单；可先执行 `/查看漫威菜单` 核对当前版本和一级菜单。凭据只用于服务端换取短期 access_token，不会写入日志。

赛季参数支持 `S0`、`S9`、`S9.5`、`S9上半赛季`、`S9下半赛季`，并支持 `s/S` 大小写；S0 没有半赛季。后台会自动转译为国服接口代码。英雄查询只接受映射表中的中文名称，例如 `/英雄 蜘蛛侠 1287101468 s9.5`，不再接受英雄代码。

地图相关字段按命名空间分别处理：`gameModeId` 表示快速、竞技、自定义或街机队列；`matchMapId` 表示地图；`playModeId` 仅作为独立玩法编号保留。已确认的常规与特殊地图会显示国服名称和玩法，快速与竞技地图 ID 分别保存；未确认编号会显示 `未知地图（ID xxxx）`，不会根据编号递增关系猜测。

代码中的 `RIVALSMETA_SEASON_MAP` 仅记录 RivalsMeta 的赛季编号体系，不用于解释国服接口中的 `matchSeason` 或 `rankGameSeason`。

## 配置

复制 `.env.example` 中的变量到 AstrBot 运行环境：

```text
MRCN_API_BASE_URL=https://s3.game.163.com/35a06fa941672d97
MRCN_REQUEST_BODY_TEMPLATE={"roleId":"{uid}"}
MRCN_HEADERS_JSON={"User-Agent":"Mozilla/5.0"}
```

如果抓包显示字段不是 `roleId`，例如 `aid`，只改模板即可：

```text
MRCN_REQUEST_BODY_TEMPLATE={"aid":"{uid}","zoneId":16001}
```

认证头只通过 `MRCN_HEADERS_JSON` 注入，建议放在 AstrBot 的环境变量或密钥管理中，不要写入插件文件。接口路径可以通过对应的 `MRCN_*_PATH` 覆盖。插件默认不假设最近比赛接口已经确认。

## 本地验证

```powershell
python -m unittest discover -s tests -v
python -m marvel_rivals_bot.cli --env-file .env.capture player 195963667
python -m marvel_rivals_bot.cli --env-file .env.capture player 195963667 --season S9
python -m marvel_rivals_bot.cli --env-file .env.capture hero 蜘蛛侠 195963667 --season s9.5
```

## 使用 mitmproxy 抓取接口

先安装 mitmproxy，然后在本目录启动采集器：

```powershell
mitmdump -s tools/mitm_capture.py --set capture_dir=captures
```

首次运行后按 mitmproxy 提示安装证书。让微信桌面端走系统代理 `127.0.0.1:8080`，打开漫威争锋国服小程序并依次执行：战绩查询、英雄详情、最近比赛、单局详情。采集器会识别 `s3.game.163.com` 下的已知接口和包含 `match`、`battle`、`history`、`record`、`recent` 的路径。

输出文件：

```text
captures/flows.json       # 脱敏请求/响应样本
captures/mrcn_config.json # 自动提取的插件配置
```

默认会脱敏 Cookie、Authorization、Token、Sign 等请求头。若要进行一次本地实时 PoC，可在确认目录权限后使用：

```powershell
$env:MRCN_CAPTURE_INCLUDE_SENSITIVE="1"
mitmdump -s tools/mitm_capture.py --set capture_dir=captures
```

抓完后应用配置：

```powershell
python tools/apply_capture.py
$env:MRCN_CAPTURE_CONFIG="D:\MR-bot\captures\mrcn_config.json"
```

敏感配置只应保存在本机，不要提交到代码库或发到群聊。

CLI 会执行真实请求；没有配置有效 API 时应返回明确的配置或 HTTP 错误，而不是静默输出假数据。

### 导出原始响应

当接口调用成功但终端没有展示字段时，使用 `--raw-output` 保存完整响应。输出仅包含接口 JSON，不包含请求头和 `access_token`：

```powershell
python -m marvel_rivals_bot.cli --env-file .env.capture --raw-output debug-responses/player.json player 195963667
python -m marvel_rivals_bot.cli --env-file .env.capture --raw-output debug-responses/recent.json recent 195963667
python -m marvel_rivals_bot.cli --env-file .env.capture --raw-output debug-responses/hero-1066.json hero 1066 195963667
python -m marvel_rivals_bot.cli --env-file .env.capture --raw-output debug-responses/match.json match 65930926_1786278432_1413197_16001_0
```

`debug-responses/`、`.env.capture`、抓包文件、SQLite 数据库和日志均已加入根目录 `.gitignore`。

## 安装到 AstrBot

将 `astrbot_plugin_marvel_rivals` 整个目录复制到 AstrBot 的插件目录，目录名保持为 `astrbot_plugin_marvel_rivals`，然后重载插件。该目录已包含核心包、`metadata.yaml`、`_conf_schema.json` 和插件内 `requirements.txt`，可独立安装。插件依赖 AstrBot 提供的 `astrbot.api`，不在普通单元测试中导入。

在 AstrBot WebUI 的插件配置中至少填写 `MRCN_ACCESS_TOKEN`。默认接口地址、路径和请求模板已经内置；生产环境通常不应配置 mitmproxy 的 `MRCN_PROXY` 或 `MRCN_CA_CERT`。QQ 接入需要 AstrBot 已配置可用的 OneBot v11/aiocqhttp 适配器（例如 NapCat）。绑定数据保存在 AstrBot 的 `data/plugin_data/astrbot_plugin_marvel_rivals/bindings.sqlite3`，插件升级不会覆盖。

手动安装后应依次验证：插件无加载错误、`/漫威帮助` 可响应、`/战绩 <UID>` 可查询、`/绑定漫威 <UID>` 后省略 UID 仍可查询。发布到插件市场前，还需要为 `metadata.yaml` 填写真实的 HTTPS GitHub `repo` 地址，并从发布包中排除 `__pycache__`、`.env*`、抓包和调试响应。

新增命令：

```text
/对局 <matchUid>
/英雄 <英雄名称> [UID] [赛季名称]
```

二维码分享页抓包已确认：`access_token` 用于接口鉴权，查询目标由 `roleId/playerUid` 指定。查询流程先调用 `GET /api/role/loadByRoleId?roleId={uid}`，随后在 `loadData`、`loadCareer`、`loadSortHero`、`loadHeroCareer` 等请求中传入同一个 `playerUid`。当前实现已按此流程查询其他公开玩家，并校验响应中的 `aid/playerUid` 与请求 UID 一致。

`loadSummaryDetail` 的请求体是 `{"matchUids":["..."]}`；`loadHeroCareer` 的请求体仍使用后台转换后的英雄 ID 和赛季代码。玩家 UID 是每次查询的业务参数，不应写死在环境配置中。
