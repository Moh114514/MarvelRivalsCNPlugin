# Marvel Rivals CN AstrBot Plugin

漫威争锋国服战绩查询插件，面向 AstrBot，支持 QQ Official、NapCat/OneBot 和其他兼容的 QQ 适配器。

国服数据接口来自官方微信小程序请求。接口不是公开稳定 API，接口地址、请求头、请求体和短期 Token 都可能变化，因此本插件把这些内容放在配置中，并提供 `mitmproxy` 采集工具辅助更新配置。

## 快速开始

1. 将仓库根目录作为 AstrBot 插件目录安装。仓库根目录已经直接包含 `main.py`、`metadata.yaml`、`_conf_schema.json` 和 `requirements.txt`，不需要再套一层 `astrbot_plugin_marvel_rivals/`。
2. 按下方“抓包并获取 Token”操作，得到当前可用的接口配置。
3. 在 AstrBot WebUI 的插件配置中填写 `MRCN_ACCESS_TOKEN`，并核对接口地址、请求头、路径和请求体模板。
4. 重载插件后执行 `/帮助` 和 `/战绩 <UID>` 验证。

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
| `MRCN_CAREER_BODY_TEMPLATE` | 生涯数据请求体 | `{season}`、`{player_uid}` |
| `MRCN_SORT_HERO_BODY_TEMPLATE` | 常用英雄请求体 | `{season}`、`{player_uid}` |
| `MRCN_HERO_BODY_TEMPLATE` | 英雄详情请求体 | `{hero_ids}`、`{season}`、`{player_uid}` |
| `MRCN_SUMMARY_DETAIL_BODY_TEMPLATE` | 对局详情请求体 | `{match_uids}` |

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
/战绩 [UID] [赛季]
/查询 [UID] [赛季]
/最近对局 [UID] [赛季]
/英雄数据 <英雄名称> [UID] [赛季]
/英雄环境 [段位] [赛季]
/英雄排行 <胜率|选取率|Ban率|场次> [段位] [赛季]
/英雄统计 <英雄名称> [段位] [赛季]
/对局详情 <matchUid>
/卡片测试
```

已绑定账号后，`UID` 可以省略：

```text
/绑定账号 1287101468
/战绩
/英雄数据 蜘蛛侠 S9.5
/英雄环境 大师 S9.5
/英雄排行 Ban率 天神 S9.5
/英雄统计 曼蒂斯 大师 S9.5
/最近对局 S9下半赛季
```

支持的赛季写法：`S0`、`S9`、`S9.5`、`S9上半赛季`、`S9下半赛季`，不区分 `s/S` 大小写。Meta 段位支持全段位、单段位，以及 `钻石+`、`大师+`、`天神+`、`永恒+`；输出统一使用国服段位名称。`/英雄环境` 只接受段位和赛季，展示胜率、选取率、Ban率、场次四个 TOP5 总览；`/英雄排行` 必须且只能指定一个排序指标，且不接受英雄名称；`/英雄统计` 接受英雄名称、段位和赛季，不接受排序指标。英雄命令使用中文英雄名称，不使用数字英雄 ID。`/帮助` 是本插件帮助，AstrBot 内置 `/help` 也会根据命令说明列出功能。

旧命令仍保留兼容：`/漫威帮助`、`/绑定漫威`、`/解绑漫威`、`/最近`、`/英雄`、`/对局`。

全局英雄环境数据来自第三方 RivalsMeta，不代表网易或 Marvel 官方统计。Meta 数据按赛季缓存到 AstrBot 的 `data/plugin_data/astrbot_plugin_marvel_rivals/meta/`；上游暂时不可用时会在有效期内展示最近缓存，并明确标记 stale 状态。英雄、段位和赛季使用统一 Game Reference；CN 细分段位会在服务边界转换为 Meta 大段位，CN 与 RivalsMeta 的赛季编号保持独立。Meta 三个查询默认生成统一视觉图片，渲染失败时回退文本；皮肤、段位人口、Tier、地图/Team-Up 和高级 Meta 查询属于后续阶段。

QQ Official 查询和 `/帮助` 会生成统一视觉的信息图片；只有 `/最近对局` 会附带用于选择单局的卡片按钮。其他查询不再发送无意义的 Markdown 或导航按钮；不支持富消息或发送失败时会回退为图片/普通文本。群聊中会自动 @ 命令发起者。绑定数据保存在 AstrBot 的 `data/plugin_data/astrbot_plugin_marvel_rivals/bindings.sqlite3`。

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
