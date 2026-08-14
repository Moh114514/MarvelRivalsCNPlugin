# 运行时图片 Asset Cache

本项目的远程英雄图片采用“本地缓存 + 可选预热 + 查询时懒加载”的架构。图片是运行时数据，不是插件发布内容。

## 数据位置

默认目录为：

```text
data/plugin_data/astrbot_plugin_marvel_rivals/assets/
├── heroes/
│   ├── 1036.webp
│   └── ...
└── manifest.json
```

插件更新不会覆盖这个目录，发布 ZIP 也不会包含它。只有明确配置 `MRCN_ASSET_CACHE_DIR` 时才会使用自定义目录；生产环境建议保留默认的 AstrBot `plugin_data` 路径。

## AssetManager 边界

`rendering/assets.py` 中的 `AssetManager` 只负责远程 URL、本地文件和 manifest 之间的转换，不负责 HTML 或 PNG 渲染：

- `get_hero_image(hero_id, image_url=None)`：优先返回本地路径；提供当前 URL 时按 URL 和更新时间执行懒加载或重新校验；
- `refresh_hero(hero_id, image_url)`：强制刷新单张图片；
- `warmup(heroes)` / `refresh_all(heroes)`：对 `hero_id -> image_url` 集合做尽力预热；
- `get_hero_data_uri(...)` / `to_data_uri(...)`：把缓存文件读成浏览器可直接使用的 Data URI；
- `status()`、`clear_cache()`：供管理端、开发工具或后台维护使用，不注册为普通玩家指令。

Renderer 不应直接发起图片网络请求。图片缺失、下载失败、缓存目录不可写或预热部分失败时，调用方必须继续使用 CSS-only 页面或现有文本回退。

## manifest

`manifest.json` 至少记录以下字段：

```json
{
  "version": 1,
  "heroes": {
    "1036": {
      "hero_id": "1036",
      "file": "heroes/1036.webp",
      "source_url": "https://cdn.example/hero.webp",
      "content_type": "image/webp",
      "fetched_at": "2026-08-14T03:00:00+00:00",
      "etag": "...",
      "last_modified": "...",
      "sha256": "..."
    }
  }
}
```

URL 变化会触发更新；URL 未变化时默认每 30 天重新校验一次，并在存在时发送 `If-None-Match` 和 `If-Modified-Since`。服务端返回 `304` 时只更新校验时间，不重复写入图片。

下载使用最多 4 个并发任务，先写入同目录临时文件，再通过 `os.replace()` 原子替换。只接受可识别的 PNG、JPEG、GIF、WebP 或 AVIF 文件签名，不把 HTML 错误页当作图片缓存。

## 启动与预热

插件初始化只创建缓存管理器，不同步下载图片，也不会因为预热失败而阻止插件加载。只有在数据源实际提供完整的 `hero_id + image_url` 集合时，才应由后台生命周期调用 `warmup()`；如果图片 URL 只在玩家或英雄查询响应中出现，则在查询路径把当前 URL 交给 `get_hero_image()`，让缓存逐步积累。

当前国服响应模型尚未确认一个稳定的全量英雄图片元数据接口，因此本阶段只提供缓存基础设施，不猜测接口路径或字段，也不主动制造几十次启动请求。英雄图片接入页面时，应先从已确认的响应字段提取 URL，再把本地文件转成 Data URI 交给页面 builder。

## 配置

| 配置 | 默认值 | 作用 |
| --- | ---: | --- |
| `MRCN_ASSET_CACHE_DIR` | 空 | 自定义缓存目录；为空使用 AstrBot `plugin_data` |
| `MRCN_ASSET_REFRESH_DAYS` | `30` | 缓存远程图片的重新校验间隔 |
| `MRCN_ASSET_MAX_CONCURRENCY` | `4` | 预热时的最大并发下载数 |
| `MRCN_ASSET_TIMEOUT_SECONDS` | `10` | 单张图片下载超时时间 |

这些配置不包含 Token。图片请求不会把国服接口的临时鉴权凭据自动转发给 CDN。

## 发布边界

不要把官方英雄图、地图图或 `data/plugin_data` 下的缓存复制到仓库。第一版不重新编码图片、不引入 Pillow，也不修改 `tools/release.py` 的发布白名单；运行时缓存与 Release ZIP 是两个独立生命周期。
