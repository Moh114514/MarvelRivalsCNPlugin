# Marvel Rivals CN AstrBot Plugin

这是一个面向 AstrBot + NapCat/OneBot 的漫威争锋国服查询插件骨架。国服接口来自官方微信小程序抓包，目前已知接口前缀和接口路径，但请求体、认证头和最近比赛接口仍需以抓包结果为准，因此没有把临时 Cookie 或 Token 提交到代码库。

## 当前命令

```text
/漫威帮助
/绑定漫威 <UID>
/解绑漫威
/战绩 [UID]
/查询 [UID]
/最近 [UID]
```

`/战绩` 和 `/查询` 当前调用 `loadData`、`loadSummary`、`loadCareer`、`loadSortHero`，并输出可用的玩家、段位、综合数据和常用英雄字段。`/最近` 会调用可配置的最近比赛接口；抓包确认后设置 `MRCN_MATCHES_PATH` 即可启用。

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
python -m marvel_rivals_bot.cli 195963667
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

## 安装到 AstrBot

将 `astrbot_plugin_marvel_rivals` 整个目录复制到 AstrBot 的插件目录，目录名保持为 `astrbot_plugin_marvel_rivals`，然后重载插件。该目录已包含核心包、`metadata.yaml`、`_conf_schema.json` 和插件内 `requirements.txt`，可独立安装。插件依赖 AstrBot 提供的 `astrbot.api`，不在普通单元测试中导入。

新增命令：

```text
/对局 <matchUid>
/英雄 <heroId> [UID]
```

截图已确认 `loadSummaryDetail` 的请求体是 `{"matchUids":["..."]}`，`loadHeroCareer` 的请求体是 `{"heroIdList":[1066],"matchSeason":"19"}`。`loadData` 等接口的请求体不包含 UID，当前 token 的账号范围仍需通过多账号抓包确认。
