# Media Manager 项目交接文档

> **目标读者**:接手本项目的下一个 agent / 开发者
>
> **本文档目的**:让你 30 分钟内理解整个项目的架构、约定、扩展点,然后能上手做事。
>
> **最后更新**:2026-05-25(对应 commit `9d953bc` 之后)

---

## 0. 项目一句话定位

**部署在群晖 NAS 上的轻量级媒体管理系统**:扫描本地视频 → 自动解析标题 → 入库 → 网页 / 外部播放器播放,顺带管理下载(qBittorrent)、搜索源(Torznab/Jackett)、Jellyfin 集成。**核心定位是"主入口",Jellyfin 只是可选播放目标之一**。

---

## 1. 5 分钟快速上手

### 启动环境
```bash
# 后端
cd backend
python3 -m venv .venv  # 第一次
source .venv/bin/activate
pip install fastapi 'uvicorn[standard]' sqlmodel pydantic-settings apscheduler httpx \
    python-multipart aiofiles 'argon2-cffi>=23.1.0' 'pyjwt>=2.10.0'
uvicorn app.main:app --reload --port 8000

# 前端 (另一终端)
cd frontend && npm install && npm run dev
# 访问 http://localhost:5173 (vite proxy /api → 8000)
```

### 默认账号
本地测试库的账号是 `admin / admin`(只是测试账号,生产环境会进入 setup 引导)。

### 后端日志
```bash
tail -f /tmp/media-manager-backend.log
```

### 自动化测试 (playwright headless)
```bash
NODE_PATH=/Users/bl/.npm/_npx/<some-hash>/node_modules \
  node /tmp/test-xxx.js
# 模板见 /tmp/test-player.js, /tmp/test-thumbnails.js, /tmp/test-parsers.js
```

---

## 2. 仓库结构

```
media-manager/
├── README.md                    # 项目主介绍
├── Dockerfile                   # 多阶段构建,前端用 BUILDPLATFORM 跑 amd64
├── docker-compose.yml           # 默认拉 ghcr.io 远程镜像 + 可选 Watchtower
├── .env.example                 # 部署模板 (JWT_SECRET 必改)
├── .github/workflows/
│   └── docker-publish.yml       # CI: master push → 自动 build & push ghcr.io
├── docs/tutorials/
│   ├── jackett-prowlarr_cn.md   # 搜索源配置
│   ├── synology-deploy_cn.md    # NAS 部署 + Watchtower
│   └── handover_cn.md           # 本文件
│
├── backend/                     # Python FastAPI
│   ├── pyproject.toml           # 依赖声明
│   ├── .env.example
│   └── app/
│       ├── main.py              # 入口 (lifespan: 迁移 / ffmpeg 检查 / 启动 worker)
│       ├── core/
│       │   ├── config.py        # pydantic-settings 配置
│       │   ├── deps.py          # FastAPI 依赖: require_user, require_admin
│       │   ├── security.py      # JWT 签发/验证, argon2 密码哈希
│       │   ├── streaming.py     # HTTP Range 流响应 + 中文文件名 (RFC 5987)
│       │   ├── file_types.py    # 视频/字幕/图片扩展名分类
│       │   └── logging.py
│       ├── api/                 # 路由层 (薄,业务下沉到 services)
│       │   ├── __init__.py      # api_router 聚合 + 鉴权依赖装配
│       │   ├── auth.py          # 登录 / 用户管理 / setup
│       │   ├── library.py       # 资源 CRUD + 批量
│       │   ├── library_tools.py # 解析器 + 重复检测
│       │   ├── files.py         # stream / subtitle / probe / stream-token
│       │   ├── playback.py      # 播放选项 / 历史 / 续播 / 目标
│       │   ├── scan.py          # 扫描路径 / 任务
│       │   ├── search.py        # 搜索源 + 聚合搜索 + FTS5
│       │   ├── downloads.py     # qBittorrent 配置 + 任务 + 去重
│       │   ├── jellyfin.py
│       │   ├── thumbnails.py    # 静态接口 (公开,严格校验)
│       │   ├── stats.py         # Dashboard 统计
│       │   ├── authors.py / media_types.py / tags.py / settings.py / health.py
│       ├── models/              # SQLModel 定义
│       │   └── __init__.py      # 所有表(共 21 张)
│       ├── db/
│       │   ├── session.py       # engine + WAL + 外键 + 缓存 PRAGMA
│       │   ├── migrate.py       # 轻量 SQL 迁移执行器 (无 Alembic)
│       │   └── migrations/
│       │       ├── 0001_init.sql        # 18 张业务表 + FTS5
│       │       ├── 0002_seed.sql        # 类型/标签/播放目标默认数据
│       │       └── 0003_auth.sql        # user / revoked_token
│       ├── services/            # 业务逻辑
│       │   ├── scan_service.py        # 扫描+入库主流程
│       │   ├── filename_parser.py     # 薄 shim,实际逻辑在 providers/parser
│       │   ├── parser_config.py       # 解析器配置持久化 (settings 表)
│       │   ├── ffprobe_service.py     # ffprobe 探测 + ffmpeg 缩略图
│       │   ├── thumbnail_service.py   # 缩略图路径管理
│       │   ├── duplicate_service.py   # 去重 (下载前 + 资源库扫描)
│       │   ├── search_service.py      # FTS5 索引同步
│       │   └── hashing.py             # partial_hash (头 1MB + 尾 1MB)
│       ├── providers/           # 适配器(可扩展点!)
│       │   ├── parser/          # 文件名解析器 ⭐ 新功能在这里加
│       │   ├── search/          # Torznab / 未来 RSS 等
│       │   ├── downloader/      # qBittorrent / 未来 Transmission 等
│       │   └── player/          # Jellyfin / 未来 Plex 等
│       └── tasks/
│           ├── scan_worker.py     # asyncio.Queue 单消费者扫描
│           └── download_sync.py   # 5s 轮询 qB 状态
│
└── frontend/                    # Vue 3 + TypeScript
    ├── package.json
    ├── vite.config.ts           # /api proxy → :8000
    └── src/
        ├── main.ts
        ├── App.vue
        ├── api/                 # axios 封装 + 各模块 API
        │   ├── http.ts          # 401 自动刷新单飞 + 拦截器
        │   ├── auth.ts / media.ts / files.ts / playback.ts / scan.ts
        │   ├── search.ts / downloads.ts / stats.ts
        │   ├── libraryTools.ts  # 解析器 + 重复检测 API
        │   └── ...
        ├── store/auth.ts        # Pinia (token / 用户态)
        ├── router/index.ts      # Vue Router + setup/login 守卫
        ├── layouts/MainLayout.vue
        ├── components/
        │   ├── PlayerDialog.vue       # Artplayer 弹窗
        │   └── MediaEditDialog.vue
        └── views/
            ├── Login.vue / Setup.vue
            ├── Dashboard.vue / Library.vue / MediaDetail.vue
            ├── Search.vue / Downloads.vue / Duplicates.vue
            ├── Settings.vue
            └── settings/        # 11 个设置 Tab
```

---

## 3. 关键技术约定

| 项 | 决策 | 原因 |
|---|---|---|
| 后端框架 | FastAPI + SQLModel | 与 Pydantic 同生态,类型友好 |
| ORM 风格 | **不用 relationship,显式 JOIN** | SQLModel 的 relationship 在大表/复杂查询里坑多;显式 JOIN 也方便 N+1 优化 |
| 数据库 | SQLite + WAL + FTS5 | NAS 场景够用、零运维、SQLite WAL 让扫描不阻塞 Web |
| 迁移 | 自研轻量执行器 (`db/migrate.py`) | 不引入 Alembic,纯 SQL 文件按文件名排序,`schema_version` 表记录已应用 |
| 前端 UI | Element Plus | 中文生态最完善,媒体库场景组件齐全 |
| 播放器 | Artplayer + hls.js | 中文文档好,Artplayer 5.x 已知坑见下文 |
| 鉴权 | JWT (access 15min + refresh 7d) | refresh token 旋转 + revoke 表;流接口用**短期签名 token** (1h) 走 query 参数 |
| 密码 | argon2 | OWASP 推荐 |
| 异步 | 全 async + asyncio.Queue 单消费者扫描 | SQLite 写锁单线程更稳 |
| 镜像源 | **官方源** (Dockerfile),用户可 build-arg 切国内 | CI 在国外,清华源会被拒 |

---

## 4. 数据模型(21 张表)

完整 schema 见 `backend/app/db/migrations/0001_init.sql` + `0003_auth.sql`,核心层级:

```
media_item   ←─┐  作品级:一个"东西",如《盗梦空间》
   │           │
   │ 1     n   │
   │           │
media_file ──→ file_asset   文件级:具体物理文件
                  │
                  └── 一个 media_item 可能有多个版本(1080p/4K)→ 多个 file_asset

tag, author, media_type 都是横向元数据
playback_history  播放进度
download_task     下载任务
search_result     外部搜索结果
duplicate_match   去重命中记录
scan_job/scan_log 扫描审计
media_search_fts  FTS5 虚拟表(由 services/search_service.py 同步)
```

**关键字段**:
- `file_asset.partial_hash`: 头 1MB + 尾 1MB SHA1,用于快速去重
- `file_asset.media_probe_json`: ffprobe 完整结果 JSON
- `media_item.normalized_title`: 解析器产出,小写无空格,**用于去重比对**
- `media_item.original_title`: 原始文件名 stem,**重解析全部时的输入**
- `media_item.cover_path`: `/api/thumbnails/{id}.jpg`(由扫描自动生成)

---

## 5. 关键扩展点(新 agent 最该掌握的)

### 5.1 添加新的「文件名解析器」

**用例**:你看到一类文件名总解析不干净(比如 PT 站特殊命名、抖音、X 平台),想加个特化 parser。

**步骤**:
1. 在 `backend/app/providers/parser/` 下新建 `xxx_parser.py`
2. 继承 `FilenameParser`,实现 `parse(self, p: ParsedName) -> ParsedName`
3. 在 `pipeline.py` 的 `PARSERS` 字典里注册一行
4. 重启后端,前端「设置 → 解析器」会自动出现新选项

**模板**(参考 `bilibili_parser.py`):
```python
from app.providers.parser.base import FilenameParser, ParsedName

class XxxParser(FilenameParser):
    name = "xxx"
    description = "用一句话说明做什么"

    def parse(self, p: ParsedName) -> ParsedName:
        work = p.working
        # 你的清洗逻辑,只能改 working 字段
        return ParsedName(
            raw=p.raw,
            working=work,
            title=p.title,                      # default 之前不要写 title
            normalized_title=p.normalized_title,
            year=p.year,                        # 提到了就填
            ...
            applied=p.applied + [self.name],
        )
```

**约定**:
- **不要改 raw**(整条 pipeline 不变)
- **只能改 working**(下一个 parser 看到的输入)
- **default 总是兜底**,你自己 parser 不需要写 title/normalized_title
- **每个 parser 必须幂等**(连跑两次结果一样)

**测试**:
```bash
.venv/bin/python -c "
from app.providers.parser.pipeline import ParserPipeline
p = ParserPipeline.from_config(['xxx', 'default'])
print(p.parse('你的测试文件名.mp4').title)
"
```

### 5.2 添加新的「下载器」

**用例**:支持 Transmission / aria2 / BitComet。

**步骤**:
1. 在 `backend/app/providers/downloader/` 下新建文件,继承 `DownloaderProvider`
2. 实现 7 个抽象方法:`health_check / add_magnet / get / list_all / pause / resume / remove / get_files`
3. 在 `factory.py` 的 `create_provider()` 里加判断分支
4. 前端「设置 → 下载器」加选项

**注意点**:
- 方法叫 `list_all` 不是 `list`,因为 Python 内置 `list` 类型在签名里冲突(踩过坑)
- `add_magnet` 必须等 metadata 拉到再返回 task_id
- `get_files` 在下载完成后用,`download_sync.py` 自动入库逻辑依赖它

### 5.3 添加新的「搜索源」

**用例**:支持除 Torznab/Jackett 外的搜索协议,如某个 RSS 站点的特化抓取。

**步骤**:
1. `backend/app/providers/search/` 下新建,继承 `SearchProvider`
2. 实现 `search(query, limit) -> list[SearchHit]` + `health_check()`
3. 在 `factory.py` 的 `_PROVIDERS` 字典里注册
4. 前端「设置 → 搜索源」的 source_type 下拉里加新选项(`SearchSourcesTab.vue`)

### 5.4 添加新的「播放目标」

**用例**:支持 Plex 跳转、自定义协议唤起、AirPlay 等。

**步骤**:
1. 在 `backend/app/api/playback.py` 的 `_build_url()` 函数里加 case
2. 数据库已有 `playback_target` 表,通过 `0002_seed.sql` 注入新行,或前端「设置 → 播放目标」管理
3. 前端 `MediaDetail.vue` 的 `handleLocalOption()` 里加对应处理

### 5.5 数据库 Schema 演进

**绝对不要**改 `0001_init.sql`!那是初版的快照。

**正确做法**:新建 `0004_xxx.sql`:
```sql
-- 0004_add_my_field.sql
ALTER TABLE media_item ADD COLUMN my_new_field TEXT;
CREATE INDEX IF NOT EXISTS idx_xxx ON media_item(my_new_field);
```

启动时 `db/migrate.py` 会自动应用未跑过的版本。

**对应的 SQLModel**:在 `models/__init__.py` 同步加字段,Python 类型与 SQL 列保持一致。

---

## 6. 后端开发规范

### 6.1 路由分层

```python
# api/xxx.py  ← 只做 HTTP / 校验 / 串联 services,不写业务
@router.post("")
def create_xxx(payload: XxxIn, session: Session = Depends(get_session)) -> XxxOut:
    obj = xxx_service.create(session, payload)  # 业务在 service
    return XxxOut.from_orm(obj)

# services/xxx_service.py  ← 业务逻辑、DB 操作、跨表协作
def create(session: Session, payload: XxxIn) -> Xxx:
    ...
```

### 6.2 鉴权约定

`api/__init__.py` 里集中装配:

```python
api_router.include_router(health.router)            # 公开
api_router.include_router(auth.router)              # 公开
api_router.include_router(thumbnails.router)        # 公开 (图片资源)

protected = [Depends(require_user)]                 # 普通用户
api_router.include_router(library.router, dependencies=protected)
# admin only 在路由内部用 Depends(require_admin)
```

**特殊路由**:`/api/files/*/stream` 不能挂 `require_user`(因为 `<video src>` 不能发 header),**自己用 query 参数 `?token=` 验签名 token**。所以 files 路由没整体挂 `protected`,内部各 endpoint 自己声明。

### 6.3 SQLite 注意事项

- `from sqlmodel import select`,不是 `sqlalchemy.select`
- 写操作前,如果对象会跨 session 用,**先把字段值取出来**(不要传 ORM 实例,会触发 DetachedInstanceError)
- 长任务(扫描)用 `with Session(engine) as session: ...` 块,**不要复用同一个 session**

### 6.4 异步约定

- `def`(同步)用于 DB 操作,FastAPI 会自动在 threadpool 里跑
- `async def`(异步)用于 IO 密集 / 调外部服务(httpx)
- 不要在 `async def` 里直接做长 SQL(会阻塞事件循环) → 用 `await asyncio.to_thread(...)`

---

## 7. 前端开发规范

### 7.1 调 API

不要直接 `axios.get`,用 `src/api/xxx.ts` 已有的 typed 封装:

```typescript
// 添加新接口
export const xxxApi = {
  list: () => http.get<XxxItem[]>('/xxx').then(r => r.data),
  create: (payload: CreateIn) => http.post<XxxItem>('/xxx', payload).then(r => r.data),
}
```

`http.ts` 里已经处理:
- 自动注入 Authorization header(从 localStorage)
- 401 → 自动用 refresh token 续 access token,再重试原请求
- 失败的 ElMessage 错误提示

### 7.2 路由守卫

`router/index.ts` 已实现完整逻辑:
- 未登录 → 自动跳 `/login`(且 setup-required 时跳 `/setup`)
- `auth.user` 缺失 → 自动 `fetchMe()`
- 任何路由 meta 加 `public: true` 表示无需登录

### 7.3 Element Plus 注意点

- `el-dialog` + `destroy-on-close` 的初始化时序:**不要在 watch(modelValue) 里立即操作 DOM**,要在 `@opened` 事件里(这是 PlayerDialog 黑屏 bug 的真因,踩过)
- `el-table` 的 `@row-click` 在 fixed 列上不触发,加 fixed 列要用按钮单独绑事件
- `el-check-tag` 的 `type` 不接受 `default`,要 undefined

### 7.4 国际化

目前**没做 i18n**。所有文案都是中文硬编码。如果要做,推荐 vue-i18n,但暂时不在路线图。

---

## 8. CI / 部署

### 8.1 CI workflow

`.github/workflows/docker-publish.yml`:
- master push / 打 v*.*.* tag → 自动构建多架构镜像
- 推送到 `ghcr.io/boylengit/media-manager:latest` (+ 分支名 + sha-xxxx)
- 用 `--platform=$BUILDPLATFORM` 让 frontend 在原生 amd64 编译,arm64 不需要 QEMU 模拟跑 node

### 8.2 镜像可见性

`ghcr.io` 默认私有,部署到 NAS 之前必须手动设为 Public:
- 打开 https://github.com/boyLenGit/media-manager/pkgs/container/media-manager
- Package settings → Change visibility → Public

### 8.3 群晖部署

完整教程见 `docs/tutorials/synology-deploy_cn.md`。简化版:
```bash
ssh admin@nas-ip
cd /volume1/docker
mkdir media-manager && cd media-manager
# 写一个 docker-compose.yml (抄项目根目录的)
sudo docker compose up -d
```

加上 Watchtower 后,你 git push → 5-10 分钟 NAS 自动拉新镜像 + 重启。

---

## 9. 重要的"坑"档案

把踩过的坑全部记下来,避免重复踩:

### 后端

1. **DetachedInstanceError**:跨 session 持有 ORM 对象会炸。修法:在 session 关闭前把字段值取出(`sp_path = scan_path.path`)。
   - 见 `services/scan_service.py` 的 `run_scan_job`

2. **`list[str]` 注解 + 方法名 `list`**:Python 把方法名当类型用,`TypeError: 'function' object is not subscriptable`。修法:加 `from __future__ import annotations` 或者方法别叫 `list` (改成 `list_all`)。
   - 见 `providers/downloader/base.py`

3. **中文文件名 Content-Disposition**:latin-1 编码失败返回 500。修法:用 RFC 5987 `filename*=UTF-8''<percent_encoded>`。
   - 见 `core/streaming.py:_make_content_disposition`

4. **Path.stem 对中文带 . 的文件名判错**:`Path("1.苹果发布会.mp4").stem` 返回 `"1"` 而不是 `"1.苹果发布会"`,因为它把第一个 `.` 当扩展名。修法:自己写更严的扩展名识别。
   - 见 `providers/parser/pipeline.py:parse`

5. **正则 `\b` 边界在中文场景失效**:`\b1080p\b` 在 `名称1080p` 里不匹配。修法:用更宽松的边界 `(?:^|(?<=[\s._\-\[\]\(\)\{\}]))`,并在汉字-数字交界处插入空格。
   - 见 `providers/parser/default_parser.py`

6. **SQLite 多语句**:`exec_driver_sql()` 一次只执行一条,但我们的迁移文件含多条,要按 `;` 拆。
   - 见 `db/migrate.py:_split_sql_statements`

### 前端

7. **Artplayer 5.x 类型校验严格**:`customType: undefined` 会抛 `[Type Error]`。修法:按需构造 options 字典,不需要的键根本不传。
   - 见 `components/PlayerDialog.vue`

8. **ElDialog 内的容器宽高问题**:dialog 弹出动画期间 DOM 不可见,Artplayer 初始化拿到 width=0。修法:用 dialog 的 `@opened` 事件触发初始化,**不要**用 `watch(modelValue, immediate)`。

9. **vue-tsc 类型检查 + Element Plus**:`el-check-tag` 的 type 不接受 `'default'`。修法:用 `undefined`。

### CI

10. **GitHub Actions 国外 runner 拒清华 npm 镜像**:fail with `ETIMEOUT`。修法:NPM_REGISTRY 用 build-arg 控制,默认官方源。
    - 见 `Dockerfile`

11. **npm 9/10 在 docker 内的 'Exit handler never called'**:即使 exit code = 0,依赖装不全,后续 `npm run build` 失败。修法:**改用 pnpm**(corepack 启用)。
    - 见 `Dockerfile`

12. **buildx 跨架构 + npm OOM**:GitHub free runner 7GB 内存不够 QEMU 模拟 arm64 跑 npm。修法:`FROM --platform=$BUILDPLATFORM`,前端只在原生 amd64 编译,产物复制到 arm64 镜像。

---

## 10. 测试策略

目前**没有单元测试框架**(MVP 阶段省略),用的是:

- **后端集成测试**:在 backend 目录用 `.venv/bin/python -c "..."` 直接跑 service 函数验证
- **API 测试**:`curl` + `python3 -m json.tool` 手动调
- **端到端**:`/tmp/test-xxx.js` playwright headless,见已有的几个文件

**建议下一步**:
- 加 pytest + pytest-asyncio,先覆盖 `services/duplicate_service.py`、`providers/parser/*` 这种纯逻辑模块
- API 测试用 `httpx.AsyncClient` + `TestClient`
- 前端没必要追求覆盖率,关键交互(播放 / 重复检测合并)用 playwright 写几个就够

---

## 11. 当前已知问题 / TODO

按优先级排序:

### 高优

- **重解析全部资源会覆盖用户手动改过的标题** — 有警告但仍是个潜在问题。可以加个"protected" flag 跳过手改过的
- **下载完成后入库逻辑** (`tasks/download_sync.py`) 没经过真实 qBittorrent 验证。我没有真 qB 实例
- **Jellyfin 集成** 目前只跳到搜索页,没做精确 ItemId 映射(本来就是 MVP 设计,可以做更深)
- **路径穿越**:`/api/thumbnails/<filename>.jpg` 已经用严格正则防了,但 `core/streaming.py` 的 `make_file_response` 直接信任了传入路径,**因为调用方是 file_asset.path,从受信 DB 读出来**,理论安全。但如果将来允许用户 query 任意路径流式播,要重新审计

### 中优

- **多语言 i18n** 没做,全中文硬编码
- **前端 bundle 1MB**,需要 manualChunks 分包(尤其 Artplayer + hls.js 太大)
- **下载器只支持 qBittorrent**,Transmission / aria2 没做(框架已就绪,见 5.2)
- **没有单元测试**(见第 10 节)

### 低优 / 探索

- **GPU 转码**:不可网播视频实时 H.264 转码到浏览器(消耗 CPU/GPU,但能解决 MPEG-4 Part 2 / HEVC 的浏览器播不了问题)
- **海报刮削**:TMDb / Bangumi / 豆瓣 API
- **自动追更**:RSS 订阅 + 关键词 + 自动下载
- **协议助手**:`media-manager://play?path=...` 唤起本地 IINA/VLC
- **移动端 PWA**

---

## 12. 关于规范 / 风格

### Git commit message

中文 commit,前缀用 conventional commits:
```
feat(scope): 新功能简述

详细说明:
- 改动 1
- 改动 2
```

scope 一般是 `backend` / `frontend` / `ci` / `deploy` / `docs`。

### 代码注释

**写中文**(因为团队是中文的)。代码本身用英文标识符,注释用中文说明意图。

### 不要做的事

- **不要引入 Alembic** — 我们已经有轻量迁移器,不需要更复杂的工具
- **不要换 ORM** — SQLModel 已经选定
- **不要装 Redis / PostgreSQL** — NAS 场景 SQLite 够,加这些是过度工程
- **不要给前端加状态管理库**(Vuex 等),只用 Pinia 就够

---

## 13. 联系方式 / 资源

- 仓库: https://github.com/boyLenGit/media-manager
- 镜像: ghcr.io/boylengit/media-manager:latest (设为 Public 后才能直接拉)
- CI: https://github.com/boyLenGit/media-manager/actions
- API 文档: 起后端后访问 http://localhost:8000/docs (FastAPI 自动生成)

---

## 14. 快速命令速查

```bash
# 重启后端
pkill -f "uvicorn app.main:app"; sleep 1
cd backend && nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/media-manager-backend.log 2>&1 & disown

# 重启前端 dev server
pkill -f "vite"; sleep 1
cd frontend && nohup npm run dev > /tmp/media-manager-frontend.log 2>&1 & disown

# 重置数据库 (谨慎!会丢所有数据)
rm -f backend/data/media_manager.db backend/data/media_manager.db-shm backend/data/media_manager.db-wal

# 重新生成所有缩略图 (删了缩略图目录,下次扫描会重做)
rm -rf backend/data/thumbnails

# 直接看数据库
.venv/bin/python -c "
from sqlalchemy import text
from app.db.session import engine
with engine.begin() as c:
    rows = c.execute(text('SELECT id, title FROM media_item LIMIT 10')).all()
    for r in rows: print(r)
"

# 前端 build (验证 ts 类型)
cd frontend && npm run build

# 测试解析器
cd backend && .venv/bin/python -c "
from app.providers.parser.pipeline import ParserPipeline
print(ParserPipeline.from_config().parse('你的文件名.mp4').title)
"
```

---

# 给下一个 agent 的建议

1. **先跑通本地** — 装依赖、起前后端、登录看到资源库,有任何起不来都先 fix
2. **看一遍 `app/main.py` 和 `api/__init__.py`** — 理解整个项目的入口和路由组织
3. **挑一个具体扩展点动手做小功能** — 推荐先写一个新的解析器或新的搜索源 provider,是项目里最舒服的扩展点
4. **改 schema 一定走 `db/migrations/000X_xxx.sql`** — 不要改老文件
5. **遇到坑先看本文档第 9 节** — 大概率前人已经踩过

如果哪里写得不清楚或者过时了,**直接更新本文档**(它在 `docs/tutorials/handover_cn.md`)。

祝你接手顺利。
