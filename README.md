# MediaHub NAS

部署在群晖 NAS 上的轻量级资源搜索、下载、资源库管理、去重、视频播放系统。

**当前版本: v1.0** — 6 个阶段全部完成,可用于生产部署。

---

## ✨ 功能总览

### 资源管理
- 多路径扫描入库,支持递归 / 增量 / 失踪标记
- 自动从文件名解析标题 / 年份 / 清晰度 / 发布组
- 媒体探测(ffmpeg/ffprobe,可选):分辨率 / 编码 / 时长
- partial_hash 快速去重(头 1MB + 尾 1MB,几百 ms 完成)

### 资源库
- 卡片视图 + 列表视图切换
- 多维筛选侧栏:类型 / 作者 / 标签(分组)/ 观看状态 / 收藏
- 4 种排序 × 升降序
- 批量打标签 / 批量改观看状态 / 批量收藏

### 元数据
- 作者管理(支持别名)
- 资源类型管理(预置 8 种,可增删改)
- 标签管理(分组 + 自定义颜色)
- 单资源完整编辑弹窗:标题 / 类型 / 作者 / 评分 / 观看状态 / 标签 / 描述

### 播放
- **网页直放**: Artplayer + hls.js,支持 mp4/webm/m4v/HLS
- **HTTP Range** 流接口,大文件拖动进度无延迟
- **签名 URL** 鉴权,1 小时短期 token
- **续播**: 自动跳转到上次播放位置,定时上报进度
- **字幕**: 同名字幕自动识别(支持 movie.zh.srt / movie.eng.srt 格式)
- **多目标播放**: 网页 / Jellyfin 跳转 / 复制带签名链接 / 复制 SMB 路径 / 自定义协议

### 下载
- qBittorrent WebUI API 集成
- 多层去重(info_hash → magnet → 标题+大小 → 模糊匹配)
- 下载前重复提示(exact/high 自动拦截,可 force 跳过)
- 任务列表实时刷新(每 3s)
- 下载完成后自动入库

### 搜索
- **聚合搜索**: 多个搜索源并发查询
- **Torznab/Jackett/Prowlarr** 协议适配器
- **本地全文搜索**: SQLite FTS5,顶栏搜索框 200ms 防抖
- 搜索结果带重复提示(已存在 / 高度疑似 / 可能重复)

### 认证
- JWT (access 15min + refresh 7d)
- argon2 密码哈希
- 多用户 + admin/viewer 两种角色
- 首次启动 setup 引导
- 自动 token 刷新 + 401 重试单飞

### 其它
- SQLite WAL 模式,扫描不阻塞 Web
- 全异步后端,asyncio.Queue 串行扫描
- ffprobe 启动检查,缺失时只降级不阻塞
- 完整 Docker 部署支持

---

## 🛠 技术栈

| 层 | 选型 |
|---|---|
| 后端 | Python 3.11 + FastAPI + SQLModel + APScheduler |
| 数据库 | SQLite (WAL 模式) + FTS5 |
| 认证 | JWT (PyJWT) + argon2-cffi |
| 前端 | Vue 3 + TypeScript + Vite + Element Plus + Pinia |
| 播放器 | Artplayer + hls.js |
| 下载器 | qBittorrent WebUI API (httpx 异步客户端) |
| 搜索 | Torznab/Jackett 兼容协议 |
| 部署 | Docker 多阶段构建 + docker-compose |

---

## 🚀 快速部署 (推荐:Docker)

### 1. 准备

```bash
git clone <repo> mediahub && cd mediahub
cp .env.example .env

# 生成 JWT 密钥(必做!)
JWT_SECRET=$(openssl rand -hex 32)
sed -i.bak "s|change-me-in-production-use-openssl-rand-hex-32|$JWT_SECRET|" .env
```

### 2. 修改 docker-compose.yml 把媒体目录挂进容器

```yaml
volumes:
  - ./data:/app/backend/data           # 数据持久化
  - /volume1/media:/media:ro           # 你的 NAS 媒体目录(只读)
  - /volume1/downloads:/downloads      # 下载目录(可写)
```

### 3. 启动

```bash
docker compose up -d
docker compose logs -f
```

访问 `http://your-nas:8000`,首次会进入引导页创建管理员账号。

### 群晖 Container Manager 使用方式

1. 上传整个项目到 NAS,例如 `/volume1/docker/mediahub`
2. Container Manager → 项目 → 创建 → 路径选 `/volume1/docker/mediahub`
3. 选 docker-compose.yml,直接 启动
4. 在系统设置 → 「扫描路径」中添加 `/media`(对应挂载的 NAS 目录)

---

## 🧑‍💻 本地开发

### 后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi 'uvicorn[standard]' sqlmodel pydantic-settings apscheduler httpx \
    python-multipart aiofiles 'argon2-cffi>=23.1.0' 'pyjwt>=2.10.0'
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

API 文档: http://localhost:8000/docs

### 前端

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173, /api 自动代理到 8000
```

### 集成开发

```bash
# 终端 1
cd backend && uvicorn app.main:app --reload --port 8000

# 终端 2
cd frontend && npm run dev
```

### 集成构建后预览

```bash
cd frontend && npm run build
cd ../backend && uvicorn app.main:app --port 8000
# 访问 http://localhost:8000
```

---

## 📁 项目结构

```
mediahub/
├── Dockerfile                    # 多阶段构建
├── docker-compose.yml
├── .env.example
├── README.md
├── backend/
│   ├── pyproject.toml
│   └── app/
│       ├── main.py              # FastAPI 入口 + lifespan
│       ├── core/                # config / logging / security / deps / streaming / file_types
│       ├── api/                 # 14 个路由模块
│       │   ├── auth.py          # 登录 / 用户 / setup
│       │   ├── library.py       # 资源 CRUD / 批量
│       │   ├── files.py         # stream / subtitle / probe
│       │   ├── scan.py          # 扫描路径 / 扫描任务
│       │   ├── search.py        # 搜索源 + 聚合搜索 + FTS
│       │   ├── downloads.py     # qB 配置 + 任务 + 去重
│       │   ├── playback.py      # 播放选项 / 历史 / 续播 / 目标
│       │   ├── jellyfin.py      # Jellyfin 配置 + 库
│       │   ├── authors.py / media_types.py / tags.py / settings.py
│       │   └── health.py
│       ├── models/              # SQLModel 定义(20+ 张表)
│       ├── db/
│       │   ├── session.py       # WAL + 外键 + 缓存
│       │   ├── migrate.py       # 轻量迁移执行器
│       │   └── migrations/      # 0001_init / 0002_seed / 0003_auth
│       ├── services/            # 业务服务
│       │   ├── scan_service.py
│       │   ├── filename_parser.py
│       │   ├── hashing.py
│       │   ├── ffprobe_service.py
│       │   ├── duplicate_service.py
│       │   └── search_service.py  # FTS5 同步
│       ├── providers/
│       │   ├── search/          # base + torznab + factory
│       │   ├── downloader/      # base + qbittorrent + factory
│       │   └── player/          # base + jellyfin + factory
│       └── tasks/
│           ├── scan_worker.py     # asyncio.Queue 单消费者扫描
│           └── download_sync.py   # 5s 轮询 qB 状态
└── frontend/
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── main.ts
        ├── App.vue
        ├── api/                 # axios + 各模块
        ├── store/               # Pinia (auth)
        ├── router/              # 守卫 + setup 引导
        ├── layouts/MainLayout.vue   # 侧边栏 + 全局搜索 + 用户菜单
        ├── components/
        │   ├── PlayerDialog.vue     # Artplayer 弹窗
        │   └── MediaEditDialog.vue  # 资源编辑
        └── views/
            ├── Login.vue / Setup.vue
            ├── Dashboard.vue / Library.vue / MediaDetail.vue
            ├── Search.vue / Downloads.vue / Settings.vue
            └── settings/        # 10 个设置 Tab
```

---

## 🔒 安全注意事项

1. **JWT_SECRET 必须改**:用 `openssl rand -hex 32` 生成 32 字节随机值
2. **首次启动**会要求创建管理员账号,第二次启动后 setup 接口被锁定
3. **流接口签名**:1 小时有效,绑定单一 file_id,不可挪用
4. **路径白名单**:`/api/files/{id}/stream` 只能访问已扫描入库的文件,不能访问任意路径
5. **生产部署**:建议套一层 HTTPS 反代(nginx / Caddy / Traefik)

---

## 📜 合规

本系统**不内置**任何资源搜索源。所有搜索源由用户在「设置 → 搜索源」中自行配置,
请确保你下载、保存、播放的内容均为你有合法授权的资源。

---

## 🗺 后续可选增强

| 项 | 说明 |
|---|---|
| Jellyfin 精确映射 | 通过 file_path 精确找到 ItemId,而不是搜索页 |
| Plex/Emby 适配 | 复用 PlayerProvider 抽象 |
| 自动追更 | RSS 订阅 + 关键词匹配 + 自动下载 |
| 海报/元数据刮削 | TMDb / Bangumi / 豆瓣 API |
| 多设备播放历史同步 | 当前已支持,只是没专门 UI |
| 协议助手 | 让 mediahub://play?path=... 唤起本地 IINA/VLC |
| 移动端 PWA | Vue 3 已内建 PWA 支持 |
# media-manager
# media-manager
