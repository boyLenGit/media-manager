# Media Manager API 速查

> 自动从 OpenAPI spec 生成的接口列表。完整定义见 http://localhost:8000/docs (FastAPI Swagger UI)。

**鉴权**:
- 公开接口:`/api/health`, `/api/info`, `/api/auth/*`, `/api/thumbnails/*`
- 普通用户:Authorization: Bearer <access_token>(15min 过期,自动 refresh)
- 管理员:`/api/auth/users` 等需要 role=admin
- 流接口:`/api/files/{id}/stream` 用 query 参数 `?token=<stream_token>`(短期签名,1h)

---

## 认证 `/api/auth`
```
GET    /api/auth/setup-required          首次启动判断是否需要引导
POST   /api/auth/setup                   创建第一个管理员
POST   /api/auth/login                   登录
POST   /api/auth/refresh                 刷新 access token (refresh token 旋转)
POST   /api/auth/logout                  登出 (撤销 refresh token)
GET    /api/auth/me                      当前用户信息
GET    /api/auth/users                   用户列表 (admin)
POST   /api/auth/users                   创建用户 (admin)
PATCH  /api/auth/users/{id}              修改用户 (admin)
DELETE /api/auth/users/{id}              删除用户 (admin)
```

## 健康 / 系统信息
```
GET    /api/health                       健康检查 + 版本号
GET    /api/info                         应用名 / debug / 集成状态
```

## 资源库 `/api/media`
```
GET    /api/media                        列表 (筛选: q/type/author/favorite/watch_status/tag_id, 排序, 分页)
GET    /api/media/{id}                   详情 (含 files 列表)
PATCH  /api/media/{id}                   更新 (title/author/type/tags/favorite/watch_status/rating/desc)
POST   /api/media/batch-tag              批量加/删标签 (add_tag_ids / remove_tag_ids)
POST   /api/media/batch-update           批量改字段 (favorite/watch_status/type/author)
```

## 资源库工具 `/api/library`
```
# 解析器 (文件名解析 pipeline 配置)
GET    /api/library/parsers              列出所有 + 当前激活
PUT    /api/library/parsers               更新激活列表 (按顺序)
POST   /api/library/parsers/test         在线测试 (filename → 解析结果,不写库)
POST   /api/library/parsers/reparse-all  用当前 pipeline 重解析所有资源标题

# 重复检测
GET    /api/library/duplicates           扫描全库,返回所有疑似重复组 (similarity 0.7-1.0)
POST   /api/library/duplicates/merge     合并 (keep_media_id + merge_media_ids[])
POST   /api/library/duplicates/delete    从资源库删除 (media_ids[],仅删 DB 不删磁盘)
```

## 文件 `/api/files`
```
GET    /api/files/{id}                   元数据 (含真实 codec / web_playable)
GET    /api/files/{id}/probe             ffprobe 完整结果
GET    /api/files/{id}/stream-token      获取短期签名 token (返回完整 URL)
GET    /api/files/{id}/stream?token=     视频流 (支持 HTTP Range,适合 <video> 标签)
HEAD   /api/files/{id}/stream?token=     stream 但只返头 (浏览器嗅探用)
GET    /api/files/{id}/subtitles         同名字幕识别 (按 normalized_title 匹配)
```

## 缩略图 (公开)
```
GET    /api/thumbnails/{filename}.jpg    封面图 (filename 必须是数字.jpg)
```

## 扫描 `/api/scan`
```
GET    /api/scan/paths                   扫描路径列表
POST   /api/scan/paths                   添加扫描路径
PATCH  /api/scan/paths/{id}              修改
DELETE /api/scan/paths/{id}              删除
POST   /api/scan/paths/{id}/scan         触发扫描 (异步,入 asyncio.Queue)

GET    /api/scan/jobs                    扫描任务历史
GET    /api/scan/jobs/{id}               单任务详情 (进度)
GET    /api/scan/jobs/{id}/logs          任务日志
```

## 搜索 `/api/search`
```
# 搜索源 (Torznab/Jackett/Prowlarr)
GET    /api/search/sources               搜索源列表
POST   /api/search/sources               添加
PATCH  /api/search/sources/{id}          修改
DELETE /api/search/sources/{id}          删除
POST   /api/search/sources/{id}/test     连通性测试

# 实际搜索
GET    /api/search?q=xxx                 聚合搜索 (并发查询所有启用源,带去重提示)
GET    /api/search/local?q=xxx           本地资源全文搜索 (FTS5)
```

## 下载 `/api/downloads`
```
# 下载器 (qBittorrent)
GET    /api/downloads/config             获取配置 (脱敏)
PUT    /api/downloads/config             保存配置
POST   /api/downloads/test               连通性测试

# 任务
GET    /api/downloads                    任务列表 (status 筛选)
GET    /api/downloads/{id}               任务详情
POST   /api/downloads                    新建任务 (force=true 跳过去重)
DELETE /api/downloads/{id}               删除 (delete_files=true 同时删磁盘)
POST   /api/downloads/{id}/pause         暂停
POST   /api/downloads/{id}/resume        恢复
POST   /api/downloads/check-duplicate    去重预检 (下载前调用,4 级精度)
```

## 播放 `/api/playback`
```
GET    /api/playback/targets             播放目标列表
PATCH  /api/playback/targets/{id}        启用/禁用/排序

GET    /api/playback/media/{id}/options  返回该资源所有可用播放方式 (含 web_playable + 不可播原因)
GET    /api/playback/media/{id}/resume   续播位置 (返回未完成的最近 history)
GET    /api/playback/media/{id}/history  完整播放历史
POST   /api/playback/progress            上报进度 (前端每 15s 调一次,支持 completed=true 标记完成)
```

## Jellyfin `/api/jellyfin`
```
GET    /api/jellyfin/config              配置
PUT    /api/jellyfin/config              保存
POST   /api/jellyfin/test                连通性 + 服务信息
GET    /api/jellyfin/libraries           Jellyfin 媒体库列表 (含路径)
```

## 元数据 (横向)
```
GET    /api/authors                      作者列表 (含 media_count)
POST   PATCH DELETE /api/authors/{id}

GET    /api/media-types                  类型列表
POST   PATCH DELETE /api/media-types/{id}

GET    /api/tags                         标签列表 (按 group 分组)
POST   PATCH DELETE /api/tags/{id}
```

## Dashboard `/api/stats`
```
GET    /api/stats                        总览统计 (资源数/文件数/下载/收藏/未看/...)
GET    /api/stats/recent-media           最近入库列表
```

## 通用设置 `/api/settings`
```
GET    /api/settings                     所有 key-value 配置
PUT    /api/settings/{key}               写/更新单个 key (用于 SMB 主机映射等)
DELETE /api/settings/{key}
```

---

## 关键 schema 速查

### MediaItemBrief (列表项)
```typescript
{
  id, title, original_title, normalized_title,
  media_type_id, media_type_name,
  author_id, author_name,
  release_date, cover_path,            // cover_path = "/api/thumbnails/{id}.jpg"
  rating, favorite, watch_status,
  file_count, tags: [{id,name,color,group}],
  created_at, updated_at,
}
```

### PlaybackOptions (播放选项)
```typescript
{
  media_id,
  files: [{
    file_asset_id, filename, extension, missing,
    is_primary, quality, container,
    video_codec, audio_codec, duration_seconds, width, height,
    web_playable: bool,                  // 综合容器+codec 判断
    web_unplayable_reason: string|null,  // 不可播时给的精确原因
    options: [{type, label, url, available}],
  }],
  options: [...],  // 主文件的选项,简便用
}
```

### DuplicateGroup (重复组)
```typescript
{
  group_key,                             // "phash:xxxxx" / "norm:xxx" / "fuzzy:xxx"
  match_level: "exact" | "high" | "medium",
  match_reason,
  members: [{
    media_id, title, cover_path,
    file_count, total_size_bytes,
    primary_filename, primary_path,
    primary_codec, primary_container, primary_quality,
    primary_width, primary_height, primary_duration_seconds,
    primary_partial_hash,
    created_at, watch_status, favorite,
  }],
}
```

### ParsedName (文件名解析结果)
```typescript
{
  title,                                 // 清理后的标题
  normalized_title,                      // 去重比对用,小写+无空格
  year, season, episode,
  quality,                               // "1080p" / "4K" 等
  release_group,                         // "VCB-Studio" 等
  language_tags: ["中英双语", ...],
  pipeline: ["bilibili", "anime", "default"],  // 经过的解析器
}
```
