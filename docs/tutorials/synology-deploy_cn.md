# 群晖 NAS 部署 Media Manager 完整教程

> 从零开始把 Media Manager 跑在你的群晖 NAS 上,**总耗时约 15 分钟**,包含数据持久化、媒体目录映射、自动更新、HTTPS 反代等生产级配置。

---

## 阅读指南

- 第 1-3 节是必看的部署流程,完成就能跑起来
- 第 4-6 节是生产环境强烈建议的配置(自动更新、HTTPS、备份)
- 第 7-8 节是常见问题排查
- 如果你只想"快速看效果",看完 §1-§3 即可

---

# 一、部署前准备

## 1.1 检查 DSM 版本

打开 **控制面板 → 信息中心**,确认 **DSM 版本 ≥ 7.2**(自带 Container Manager,管理 docker-compose 项目)。

如果版本太旧:
- DSM 6.x:**只能用旧的 Docker 套件**,本教程的图形化步骤不适用,只能走 §3 SSH 命令行
- DSM 7.0/7.1:**升级到 7.2+** 体验最好

## 1.2 检查机型支持

打开 **Container Manager**(套件中心搜索安装),如果能打开就说明你的群晖支持 Docker。
- 大部分 +/Plus 系列、xs/Value 系列都支持
- J 系列(预算款)部分型号不支持
- 不确定看 https://www.synology.com/zh-cn/dsm/packages/ContainerManager

## 1.3 必要信息收集

部署前需要 4 个信息,**先记下来**:

| 信息 | 怎么获取 | 例子 |
|---|---|---|
| **NAS 内网 IP** | 控制面板 → 网络 → 网络界面 | `192.168.1.100` |
| **你的 NAS 用户 UID:GID** | 见下方 §1.4 | `1026:100` |
| **媒体目录的 NAS 真实路径** | File Station 看你视频在哪 | `/volume1/media` |
| **JWT 密钥**(随机 64 字符) | `openssl rand -hex 32` 或 [在线生成器](https://1password.com/password-generator/) | 64 位 hex |

## 1.4 怎么查 UID:GID

UID/GID 决定容器以哪个用户身份读写文件。**写错了会导致容器读不到媒体文件 / 无法生成缩略图**。

**方法 A:SSH(推荐)**

控制面板 → 终端机和 SNMP → 启用 SSH(顺手把端口从默认 22 改个不容易撞上的,如 2222)。

然后用 Mac/Windows 的终端 SSH 进 NAS:

```bash
ssh -p 2222 你的群晖用户名@192.168.1.100
# 输入密码进入后:
id
# 输出形如: uid=1026(boylen) gid=100(users) groups=100(users),101(administrators)
```

记下 `uid=` 和 `gid=` 后面的两个数字,例如 `1026:100`。

**方法 B:不开 SSH**

DSM 控制面板 → **用户与群组** → 选中你的用户 → 右下角隐约能看到 ID。或者用任意一台 Mac:

```bash
# 假设 NAS SMB 共享你的家目录
ls -lan /Volumes/你的SMB盘符/ | head -3
# 看 owner 的数字 ID
```

如果都不行,用 `1026:100`(群晖大多数情况下管理员账号是这个),装好后跑不通再回来调。

## 1.5 镜像在哪?

镜像托管在 GitHub Container Registry,**已经设为 Public,任何人不需要登录就能拉**:

```
ghcr.io/boylengit/media-manager:latest
```

可用版本(tag)列表: https://github.com/boyLenGit/media-manager/pkgs/container/media-manager

| Tag | 含义 | 推荐场景 |
|---|---|---|
| `latest` | 永远跟随 master 分支最新代码 | 想自动追最新版 |
| `master` | 同 latest | 同上 |
| `sha-xxxxxx` | 固定到某次 commit | 生产环境固定版本 |
| 未来 `1.0.0` 等 | 语义化版本(目前还没打 tag) | 未来稳定版用 |

**生产环境建议固定 tag**,避免半夜被自动升级踩坑。

---

# 二、部署方案选择

| 方案 | 适用 | 优点 | 缺点 |
|---|---|---|---|
| **Container Manager 图形界面** | 不熟悉 SSH 的用户 | 全程鼠标点 | 改配置需要点很多次 |
| **SSH + docker compose** | 熟手 | 命令一气呵成 / 易脚本化 | 需要先开 SSH |

**新手选图形界面 →** 跳到 §3。
**熟手或想脚本化 →** 跳到 §4。

---

# 三、方案 A:Container Manager 图形部署(推荐新手)

## 3.1 准备目录

打开 **File Station**:

1. 在 `/volume1/docker/`(没有就新建一个)下,新建文件夹 `media-manager`
2. 进入 `media-manager`,再新建子文件夹 `data`(用来存数据库和缩略图)

最终目录结构:
```
/volume1/docker/media-manager/
└── data/                           ← 数据持久化(空的)
```

## 3.2 创建 docker-compose.yml

仍然在 File Station 里:

1. 进入 `/volume1/docker/media-manager/`
2. 右键 → **新增** → **新建文件**(如果没这个选项,DSM 自带的 **Text Editor** 打开)
3. 文件名: `docker-compose.yml`
4. 粘贴下面内容,**改 4 处带 ⚠️ 的地方**

```yaml
services:
  media-manager:
    image: ghcr.io/boylengit/media-manager:latest
    container_name: media-manager
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      # ⚠️ 必改 1:JWT 密钥,执行 openssl rand -hex 32 生成 64 字符
      JWT_SECRET: "把这一长串换成你 openssl 生成的 64 个 hex 字符"

      JWT_ACCESS_TTL_MINUTES: 15
      JWT_REFRESH_TTL_DAYS: 7

      # ⚠️ 必改 2:把 IP 改成你 NAS 的局域网 IP
      CORS_ORIGINS: "http://192.168.1.100:8000"

      TZ: Asia/Shanghai
    volumes:
      # 数据持久化(必须!)
      - ./data:/app/backend/data

      # ⚠️ 必改 3:媒体目录,左边改成你视频所在的实际路径
      # 容器内统一是 /media,后面在 Web UI 添加扫描路径时填 "/media"
      - /volume1/media:/media:ro
      # 如果还想加其他目录:
      # - /volume1/photo/家庭录像:/family-videos:ro

    # ⚠️ 必改 4:改成 §1.4 查到的 UID:GID
    user: "1026:100"

    labels:
      - "com.centurylinklabs.watchtower.enable=true"
```

**注意**:`environment` 里的字符串值用双引号 `"..."` 包起来比较稳,避免特殊字符被 yaml 解析错。

## 3.3 创建项目并启动

打开 **Container Manager**(套件中心装好后在主菜单里):

1. 左侧选 **项目**(不是「容器」,是「项目」!)
2. 点右上角 **新增**
3. 配置:
   - **项目名称**: `media-manager`
   - **路径**: 点 **设置路径** → 浏览到 `/docker/media-manager`(就是你刚才建的)
   - **来源**: 选 **使用现有的 docker-compose.yml**
   - 它会自动检测到该目录下的 yml
4. 下一步 → **审阅 yml** → 确认无误 → 下一步
5. 摘要 → 选中 **创建后立即启动项目**
6. 完成

第一次会拉镜像(约 200MB),进度可以在 **Container Manager → 镜像** 里看,大约 2-5 分钟。

## 3.4 验证启动成功

回到 **项目 → media-manager**,状态应该是绿色 **运行中**。

点项目名进入,选 **日志** Tab,应该看到类似:

```
INFO  app.main           | Starting Media Manager (debug=False)
INFO  app.db.migrate     | Found 4 pending migrations.
INFO  app.db.migrate     | Applying migration: 0001_init
INFO  app.db.migrate     | ...
INFO  app.services.ffprobe_service | ffprobe found: /usr/bin/ffprobe
INFO  app.services.ffprobe_service | ffmpeg found: /usr/bin/ffmpeg
INFO  app.tasks.scan_worker | scan worker started
INFO  Application startup complete.
INFO  Uvicorn running on http://0.0.0.0:8000
```

看到 `Uvicorn running on http://0.0.0.0:8000` 就是成功了。

## 3.5 浏览器访问

```
http://你的NAS-IP:8000
```

例如 `http://192.168.1.100:8000`。

第一次访问会自动跳转到 **欢迎使用 Media Manager** 引导页:

1. 输入用户名 + 密码,点「创建管理员」
2. 跳转到主界面 → 点左侧 **设置 → 扫描路径**
3. 添加扫描路径:
   - **路径**: `/media`(对应你 docker-compose 里 volumes 右边的值)
   - **名称**: 随便,如「视频库」
   - **递归**: ✅ 打开
   - **启用**: ✅ 打开
4. 保存后点该行的 **扫描** 按钮
5. 等几秒到一分钟(看你视频数量),回到「资源库」就能看到所有视频卡片

跳到 §5 阅读自动更新配置。

---

# 四、方案 B:SSH 命令行部署(熟手)

完整脚本,**改 4 处带 ⚠️ 的变量**,然后一次性贴到 NAS 终端跑:

```bash
ssh -p 2222 你的群晖用户名@192.168.1.100

# ============================
# 一次性配置 (改这 4 个)
# ============================
NAS_IP="192.168.1.100"           # ⚠️ 你的 NAS 局域网 IP
NAS_USER_UID_GID="1026:100"      # ⚠️ id 命令查到的
MEDIA_DIR="/volume1/media"       # ⚠️ 视频目录
JWT_SECRET=$(openssl rand -hex 32)
echo "记下 JWT_SECRET: $JWT_SECRET"

# ============================
# 部署 (照抄)
# ============================
PROJ=/volume1/docker/media-manager
sudo mkdir -p "$PROJ/data"
cd "$PROJ"

# 写 docker-compose.yml
sudo tee docker-compose.yml > /dev/null <<EOF
services:
  media-manager:
    image: ghcr.io/boylengit/media-manager:latest
    container_name: media-manager
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      JWT_SECRET: "$JWT_SECRET"
      JWT_ACCESS_TTL_MINUTES: 15
      JWT_REFRESH_TTL_DAYS: 7
      CORS_ORIGINS: "http://$NAS_IP:8000"
      TZ: Asia/Shanghai
    volumes:
      - ./data:/app/backend/data
      - $MEDIA_DIR:/media:ro
    user: "$NAS_USER_UID_GID"
    labels:
      - "com.centurylinklabs.watchtower.enable=true"
EOF

# 启动
sudo docker compose up -d

# 跟踪日志确认起来
sudo docker compose logs -f media-manager
# 看到 "Uvicorn running on..." 后,Ctrl+C 退出 (容器还在跑)
```

浏览器访问 `http://NAS-IP:8000`,完成首次配置(同 §3.5)。

---

# 五、自动更新(强烈推荐)

**没自动更新会怎样?** 你 push 新代码后,GitHub Actions 自动构建新镜像到 ghcr.io,但 NAS 上的容器仍跑旧版,需要你手动 `docker compose pull` 才会更新。

**有了自动更新?** Watchtower 每天定时检查,有新版就自动 pull + 重启容器,**数据完全不丢**。

## 5.1 加入 Watchtower 服务

编辑你的 `docker-compose.yml`,在 `services:` 下追加(注意缩进,跟 `media-manager:` 同级):

```yaml
services:
  media-manager:
    # ... (前面的不动)

  # ↓↓↓ 新加这一段 ↓↓↓
  watchtower:
    image: containrrr/watchtower
    container_name: watchtower
    restart: unless-stopped
    environment:
      # 每天凌晨 4 点检查一次 (cron 格式: 秒 分 时 日 月 周)
      WATCHTOWER_SCHEDULE: "0 0 4 * * *"
      # 只更新带 com.centurylinklabs.watchtower.enable=true 标签的容器
      # 避免误升 NAS 自带服务
      WATCHTOWER_LABEL_ENABLE: "true"
      # 拉新镜像后清理旧的,节省磁盘
      WATCHTOWER_CLEANUP: "true"
      TZ: Asia/Shanghai
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
```

## 5.2 应用配置

**Container Manager**:进入项目 → 编辑 → 粘贴新内容 → 应用 → 重新部署。

**SSH**:
```bash
cd /volume1/docker/media-manager
sudo docker compose up -d
```

## 5.3 验证

```bash
sudo docker logs watchtower
# 应该看到:
#   Watchtower 1.x.x
#   Scheduling first run: ...
```

之后每天凌晨 4 点自动检查更新。

## 5.4 想立即升级一次?(不等到凌晨 4 点)

```bash
cd /volume1/docker/media-manager
sudo docker compose pull && sudo docker compose up -d
```

或者让 Watchtower 立即跑一遍:
```bash
sudo docker exec watchtower /watchtower --run-once media-manager
```

## 5.5 想固定版本不自动升级?

适用于**生产环境怕半夜被升级踩坑**。把 docker-compose.yml 里 `image:` 改成具体 commit:

```yaml
image: ghcr.io/boylengit/media-manager:sha-3e829a5
```

可用 tag 列表: https://github.com/boyLenGet/media-manager/pkgs/container/media-manager

或者把容器从 Watchtower 排除:删掉 `media-manager` 服务下的 `labels: ...watchtower.enable=true` 那一行。

---

# 六、HTTPS 反代(强烈推荐)

直接 8000 端口访问:
- 局域网内 OK
- 公网暴露 → 不安全,密码裸奔(虽然我们用了 HTTPS-only 的 cookie,但中间人仍能拿到你的 admin 密码)

**用群晖自带反代解决**:

## 6.1 准备域名 + 证书

需要先有:
- 一个域名(如 `your-domain.com`)
- 子域名指向你的 NAS 公网 IP(如 `mm.your-domain.com`)
- DSM 自动申请的 Let's Encrypt 证书:
  **控制面板 → 安全性 → 证书 → 新增 → 添加新证书 → Let's Encrypt** → 域名填 `mm.your-domain.com`

## 6.2 配置反代

**控制面板 → 登录入口 → 高级 → 反向代理服务器 → 新增**

| 配置 | 值 |
|---|---|
| 描述 | Media Manager |
| **来源** 协议 | HTTPS |
| 来源 主机名 | `mm.your-domain.com` |
| 来源 端口 | 443 |
| **HSTS** | ✅ 打开 |
| **HTTP/2** | ✅ 打开 |
| **目的地** 协议 | HTTP |
| 目的地 主机名 | `localhost` |
| 目的地 端口 | 8000 |

切到 **自定义标头** Tab → **创建 → 选择 WebSocket** → 自动加 4 行(虽然我们暂时没用 WS,加上无副作用)。

保存。

## 6.3 修改 CORS_ORIGINS

反代之后,前端的"源"变成了 `https://mm.your-domain.com`,要把它加到 CORS 白名单。

编辑 `docker-compose.yml`,改 `CORS_ORIGINS`:

```yaml
CORS_ORIGINS: "http://192.168.1.100:8000,https://mm.your-domain.com"
```

应用配置:
```bash
cd /volume1/docker/media-manager
sudo docker compose up -d
```

## 6.4 验证

浏览器:

```
https://mm.your-domain.com
```

应该自动是 HTTPS、绿锁、跳到 Media Manager 登录页。

---

# 七、备份与恢复

## 7.1 唯一需要备份的目录

```
/volume1/docker/media-manager/data/
├── media_manager.db          ← SQLite 数据库 (用户/资源/标签/配置)
├── media_manager.db-wal      ← WAL 副文件 (一起备!)
├── media_manager.db-shm      ← SHM 副文件 (一起备!)
└── thumbnails/               ← 视频缩略图 (丢了重扫会重新生成,可不备)
```

媒体源文件本身(`/volume1/media`)是只读挂载,**Media Manager 不会动它们**,按你 NAS 自己的备份策略处理。

## 7.2 用 Hyper Backup 备份

**Hyper Backup**(套件中心装) → 数据备份任务 → 新增:

1. 备份目标:USB 硬盘 / Synology C2 / 其他云
2. 数据源勾选: `/volume1/docker/media-manager/data/`
3. 调度:每天 00:00 (反正容器深夜没活动)
4. 设置版本数:7 天滚动够用

## 7.3 灾难恢复

NAS 重装了 / 数据库损坏了:

```bash
# 1. 重新部署容器 (按本教程 §3 / §4)
# 2. 容器还没启动前,把备份的 data/ 目录还原回去
# 3. 启动容器,所有用户、资源、配置全部恢复
```

## 7.4 从旧版 MediaHub 升级会不会丢数据?

**不会。** Media Manager v0.x 启动时会**自动**把旧的 `mediahub.db` 改名为 `media_manager.db`(包括 WAL/SHM 副文件)。看启动日志能看到:

```
Found legacy database data/mediahub.db, renaming to data/media_manager.db
(rebranding from MediaHub → Media Manager)
Legacy database migration done.
```

资源、用户、标签、配置都会保留。前端 localStorage 里的登录态也会自动迁移,**不需要重新登录**。

如果担心,部署前手动备份 `data/` 目录。

---

# 八、常见问题排查

## Q1: 容器起来但 8000 端口访问不到

**先排查防火墙**:控制面板 → **安全性 → 防火墙** → 看启用了哪条规则集 → 编辑 → 创建 → 端口 8000 → **允许**

如果防火墙没开,**确认 NAS 内网 IP 没填错**:`http://192.168.1.100:8000`(用 NAS 的局域网 IP,不是路由器的)。

## Q2: 资源库扫不到东西 / 缩略图全是字母占位符

**99% 是文件权限问题**,容器以错误的用户身份运行,读不到 `/volume1/media`。

排查:
```bash
ssh -p 2222 你的用户@NAS-IP
id                                                  # 看 uid=xxx gid=xxx
ls -lan /volume1/media | head -5                    # 看视频文件的 owner
```

如果 docker-compose.yml 里 `user: "1026:100"` 跟 `id` 输出对不上,改了重新部署:

```bash
cd /volume1/docker/media-manager
sudo docker compose down
sudo docker compose up -d
```

如果文件 owner 是个奇怪的 UID(比如 SMB 上传过来的可能是 1026, 但 NAS 有些文件夹是 root 所有),可以临时把 user 行删掉(让容器以 root 跑,有读权限但不安全),先验证功能,再回头修权限。

## Q3: 启动报 `JWT_SECRET` 默认值警告

意思是你 docker-compose.yml 里 JWT_SECRET 还是占位符。**必须改成真随机字符串**,否则任何知道默认值的人都能伪造你的 token 登录。

```bash
openssl rand -hex 32
# 输出 64 字符 hex 串,复制到 docker-compose.yml 里替换
```

## Q4: 想换 8000 端口

把 docker-compose.yml 里:
```yaml
ports:
  - "8090:8000"   # 左边是 NAS 上对外端口,右边是容器内不要动
```

同时改 `CORS_ORIGINS` 里的端口。重新部署。

## Q5: 升级后界面还是旧版

浏览器强制刷新(`Ctrl+Shift+R` / `Cmd+Shift+R`)清缓存。

或者在隐私模式打开看是不是真的旧版。

确认后端版本:
```bash
curl http://NAS-IP:8000/api/health
# {"status":"ok","version":"...","commit":"abc1234"}
```

`commit` 字段就是当前部署的 git short SHA。和 https://github.com/boyLenGit/media-manager/commits/master 对一下,如果不匹配说明 Watchtower 还没拉到新镜像或没生效,手动:

```bash
cd /volume1/docker/media-manager
sudo docker compose pull && sudo docker compose up -d
```

## Q6: Container Manager 看不到日志 / 日志一片空

切到 **容器** Tab(不是项目 Tab)→ 选 `media-manager` → 详情 → **日志**。

或者 SSH:
```bash
sudo docker logs media-manager --tail 100 -f
```

## Q7: 想完全卸载

```bash
cd /volume1/docker/media-manager
sudo docker compose down
# 删容器
sudo docker rm -f media-manager watchtower 2>/dev/null
# 删镜像
sudo docker rmi ghcr.io/boylengit/media-manager:latest containrrr/watchtower
# 删数据 (慎重!这会丢失所有用户和资源元数据)
sudo rm -rf /volume1/docker/media-manager/
```

媒体源文件不会被删(只读挂载从未被改动)。

## Q8: 添加扫描路径报错 "path_not_exists"

容器内的路径 ≠ NAS 路径。

举例:你 docker-compose.yml 里:
```yaml
volumes:
  - /volume1/media:/media:ro
```
那 Web UI 添加扫描路径时**填 `/media`,不是 `/volume1/media`**。

## Q9: 为啥镜像那么大(200MB+)?

里面打包了:
- Python 3.11 + 依赖 (~80MB)
- ffmpeg + ffprobe (~80MB,支持几乎所有视频格式探测和缩略图生成)
- 前端 Vue 构建产物 (~3MB)
- 操作系统 base layer (~30MB)

去掉 ffmpeg 镜像能小到 ~120MB,但你会失去缩略图生成功能,得不偿失。

## Q10: 我想用其他端口的 NAS(如 8000 已被 Synology 自家服务占用)

```yaml
ports:
  - "9100:8000"
```

`8000` 是常被群晖 Surveillance Station / Photo Station 占用的端口。

---

# 九、推荐技术栈组合

如果你想搭一整套自动化媒体管家,**docker-compose 一起跑**这些容器:

```
媒体管家
├─ media-manager   :8000   ← 资源库主入口(本项目)
├─ qbittorrent     :8080   ← BT 下载器
├─ prowlarr        :9696   ← 搜索源代理 (Jackett 升级版)
├─ jellyfin        :8096   ← 大文件兜底播放器(媒体服务器)
├─ flaresolverr    :8191   ← Cloudflare 验证反代 (可选)
└─ watchtower             ← 自动更新(本文 §5)
```

每个组件用独立的 docker-compose 文件管理,**避免一个文件越来越长**。例如:

```
/volume1/docker/
├── media-manager/
│   ├── docker-compose.yml
│   └── data/
├── qbittorrent/
│   ├── docker-compose.yml
│   └── config/
├── prowlarr/
│   ├── docker-compose.yml
│   └── config/
└── jellyfin/
    ├── docker-compose.yml
    └── config/
```

Prowlarr 配置看 [`docs/tutorials/jackett-prowlarr_cn.md`](./jackett-prowlarr_cn.md)。

部署完后:
1. Media Manager 设置 → 下载器 → 填 qBittorrent 的 `http://nas-ip:8080`
2. Media Manager 设置 → 搜索源 → 填 Prowlarr 的 `http://nas-ip:9696/...`
3. Media Manager 设置 → Jellyfin → 填 Jellyfin 的 `http://nas-ip:8096`

链路就打通了:
- 在 Media Manager 搜资源 → 一键加到 qBittorrent → 下完自动入库 → 网页直接播 → 网页播不了的资源点 Jellyfin 跳转转码

---

# 十、版本固定推荐(给生产环境)

如果你不想被自动升级打扰,固定到具体版本:

```yaml
image: ghcr.io/boylengit/media-manager:sha-3e829a5   # 固定 commit
```

或:
```yaml
image: ghcr.io/boylengit/media-manager:master        # 跟 master 但有缓存,刷新慢
```

或将来打 release tag 后:
```yaml
image: ghcr.io/boylengit/media-manager:v1.0.0
```

**生产环境建议**:
1. 固定到具体 commit / 语义版本
2. 不启用 Watchtower 自动升级
3. 自己评估稳定性后,手动 `docker compose pull` 升级

**家用 / 玩票建议**:
1. 用 `:latest`
2. 启用 Watchtower
3. 数据每天 Hyper Backup 备份(出问题能恢复就行)

---

# 总结流程图

```
        [你 git push 代码]
              ↓
     [GitHub Actions 自动构建]  ← 7-8 分钟
              ↓
         [ghcr.io 镜像更新]
              ↓
    [NAS Watchtower 凌晨 4 点拉]
              ↓
   [media-manager 容器自动重启]   ← 数据保留,无感升级
              ↓
        [浏览器访问 → 新版]
```

---

# 部署完成后的"5 分钟体验"

1. ✅ http://NAS-IP:8000 → 登录管理员
2. ✅ 设置 → 扫描路径 → 添加 `/media` → 扫描
3. ✅ 资源库看到所有视频卡片(自带封面)
4. ✅ 点详情页 → 网页播放可直接播 H.264 mp4
5. ✅ 设置 → 解析器 → 在线测试看你的特殊文件名能否清理干净
6. ✅ 重复检测页查找你库里有没有重复资源
7. (可选) 装 qBittorrent + Prowlarr,体验完整搜索-下载-入库链路

部署遇到任何问题,把日志贴到 https://github.com/boyLenGit/media-manager/issues
