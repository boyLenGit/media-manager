# 群晖 NAS Docker 部署教程

> 把 Media Manager 部署到你的群晖 NAS 上,从零到能用,大约 10 分钟。
>
> 适用 DSM 7.2 及以上版本(自带 **Container Manager**)。

---

## 0. 前提条件

- 群晖 NAS,DSM 版本 ≥ 7.2(套件中心搜 "Container Manager" 能看到才行)
- NAS 能访问外网(拉镜像和后续自动更新需要)
- 你能 SSH 进 NAS,**或者**会用 DSM 控制面板管文件

---

## 1. 镜像在哪

镜像托管在 GitHub Container Registry,**完全免费、公开访问**:

```
ghcr.io/boylengit/media-manager:latest
```

不需要登录 GitHub 就能拉。

---

## 2. 方案 A:Container Manager 图形界面(推荐新手)

### 2.1 准备目录

打开 **File Station** → 在 `/volume1/docker/`(没有就新建)下创建文件夹 `media-manager`。

进去再建子目录 `data`(用来存数据库和缩略图)。

最终结构:
```
/volume1/docker/media-manager/
└── data/
```

### 2.2 写 docker-compose.yml

仍然在 File Station 里,在 `media-manager` 目录里新建文件 `docker-compose.yml`:

```yaml
services:
  media-manager:
    image: ghcr.io/boylengit/media-manager:latest
    container_name: media-manager
    restart: unless-stopped
    ports:
      - "8000:8000"            # 左边端口被占用就改成 8090 等
    environment:
      # JWT 密钥 - 必改! 随便复制 64 个字符,或在 NAS SSH 里执行 openssl rand -hex 32
      JWT_SECRET: "把-这-串-换-成-你-自-己-的-64-字-符-随-机-串-至-少-32-位"
      JWT_ACCESS_TTL_MINUTES: 15
      JWT_REFRESH_TTL_DAYS: 7
      CORS_ORIGINS: "http://你的NAS-IP:8000"
      TZ: Asia/Shanghai
    volumes:
      - ./data:/app/backend/data           # 数据持久化(必须!)
      # 下面是要扫描的媒体目录,改成你 NAS 上的真实路径
      # 左 = NAS 真实路径, 右 = 容器内路径(填什么都行,后面在 Web 设置里加这个右边的值即可)
      - /volume1/media:/media:ro           # 视频库,只读
      # - /volume1/downloads:/downloads:rw # 下载目录(可选)
    user: "1026:100"            # 改成你 NAS 用户的 UID:GID(2.4 节会教你怎么查)
    labels:
      - "com.centurylinklabs.watchtower.enable=true"
```

**3 处必改的地方**:

| 字段 | 改什么 |
|---|---|
| `JWT_SECRET` | 任意 64 字符随机串,生产环境必须改 |
| `CORS_ORIGINS` | 把 `你的NAS-IP` 换成实际 IP,例如 `http://192.168.1.100:8000` |
| `volumes` 媒体路径 | 左侧改成你视频实际放的目录 |
| `user` | 改成你 NAS 用户的 UID:GID(2.4 节) |

### 2.3 用 Container Manager 创建项目

1. 打开 **Container Manager**(套件中心搜不到就升级 DSM 或装一下)
2. 左侧选 **项目** → 点 **新增**
3. **项目名称**: `media-manager`
4. **路径**: 点浏览,选 `/docker/media-manager`(就是你刚才建的)
5. **来源**: 选 **使用现有的 docker-compose.yml**
6. 它会自动识别同目录下的 yml 文件
7. 下一步 → 摘要确认 → 完成
8. 它会问要不要立即启动,选 **启动**

第一次会拉镜像,大约 200MB,几分钟即可。

### 2.4 怎么查 UID:GID(给 user 字段填的)

打开 **控制面板 → 终端机和 SNMP** → 启用 SSH。

然后用任意 SSH 工具(Terminal / Putty)连进 NAS:

```bash
ssh 你的用户名@NAS-IP
id
# 输出形如: uid=1026(admin) gid=100(users) groups=100(users),...
# 把 docker-compose.yml 里的 user: "1026:100" 改成你看到的数字
```

修改后回到 Container Manager → 选中项目 → 重新部署。

### 2.5 验证

浏览器访问:

```
http://你的NAS-IP:8000
```

第一次进来会看到 **欢迎使用 Media Manager** 页面,创建管理员账号即可。

---

## 3. 方案 B:SSH 命令行(推荐熟手)

```bash
# 1. SSH 进 NAS
ssh 你的用户名@NAS-IP

# 2. 准备目录
sudo mkdir -p /volume1/docker/media-manager/data
cd /volume1/docker/media-manager

# 3. 生成 JWT 密钥
JWT=$(openssl rand -hex 32)
echo "记下这个 JWT_SECRET: $JWT"

# 4. 查 UID:GID
id

# 5. 创建 docker-compose.yml
sudo nano docker-compose.yml
# 粘贴 2.2 节的内容,把 JWT/IP/UID:GID/媒体路径改好,Ctrl+X → Y → Enter 保存

# 6. 启动
sudo docker compose up -d

# 7. 看日志确认起来了
sudo docker compose logs -f media-manager
# 看到 "Application startup complete." 和 "Uvicorn running on..." 就成功了
# Ctrl+C 退出日志查看(容器还在跑)
```

浏览器访问 `http://你的NAS-IP:8000`。

---

## 4. 首次配置

进入 Web UI 后:

### 4.1 创建管理员账号

第一次访问会自动跳到 setup 页面,填用户名 + 密码即可。**第二次启动后这个引导接口会被锁住**。

### 4.2 添加扫描路径

**设置 → 扫描路径 → 添加路径**:

- **路径**: 容器内路径,即 docker-compose.yml 中 volumes 右边那个值,例如 `/media`
- **名称**: 随便,如 `电影库`
- **递归**: 打开
- **启用**: 打开

保存后点该行的 **扫描** 按钮。等几秒,你的视频会出现在「资源库」页面。

### 4.3 给视频生成缩略图

镜像内置 ffmpeg,**第一次扫描会自动**给所有视频抽帧生成封面。如果你看到资源卡片是字母占位符,说明扫描可能因权限问题失败了 — 检查 `user:` 字段配置(见第 2.4 节)。

---

## 5. 自动更新(可选,推荐)

### 5.1 启用 Watchtower

回到你的 docker-compose.yml,在 `services:` 下面追加:

```yaml
  watchtower:
    image: containrrr/watchtower
    container_name: watchtower
    restart: unless-stopped
    environment:
      WATCHTOWER_SCHEDULE: "0 0 4 * * *"   # 每天凌晨 4 点检查
      WATCHTOWER_LABEL_ENABLE: "true"      # 只更新带标签的容器(避免误升 NAS 自带服务)
      WATCHTOWER_CLEANUP: "true"           # 清理旧镜像
      TZ: Asia/Shanghai
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
```

注意 `media-manager` 服务那里已经有 `labels: com.centurylinklabs.watchtower.enable=true`,Watchtower 看到这个标签才会管它。

应用配置:

- Container Manager:项目 → 编辑 → 应用 → 重新部署
- SSH:`sudo docker compose up -d`

### 5.2 验证 Watchtower 在跑

```bash
sudo docker logs watchtower
# 应该看到类似 "Watchtower starting" 和 "Session done"
```

之后每天凌晨 4 点,Watchtower 自动检查 ghcr.io 上的 latest tag 是不是有新版,有就拉下来重启容器。**数据(`./data` 目录)不会丢**。

### 5.3 想立即升级一次

```bash
cd /volume1/docker/media-manager
sudo docker compose pull && sudo docker compose up -d
```

或者让 Watchtower 立即跑一轮:

```bash
sudo docker exec watchtower /watchtower --run-once media-manager
```

---

## 6. 常用运维命令

```bash
cd /volume1/docker/media-manager

# 查容器状态
sudo docker compose ps

# 看日志(跟随)
sudo docker compose logs -f media-manager

# 重启
sudo docker compose restart media-manager

# 停止 + 启动
sudo docker compose down
sudo docker compose up -d

# 看后端跑的版本号
curl http://NAS-IP:8000/api/health
# 返回 {"status":"ok","version":"...","commit":"..."}

# 进容器看
sudo docker exec -it media-manager bash
# 退出: exit
```

---

## 7. 反向代理 + HTTPS(强烈建议)

直接暴露 8000 端口不安全,容易被局域网或公网扫描。建议用群晖的反向代理:

1. **控制面板** → **登录入口** → **高级** → **反向代理服务器** → **新增**
2. **来源**:
   - 协议: HTTPS
   - 主机名: `media-manager.你的域名` (你需要先有域名 + DSM 自带 Let's Encrypt 证书)
   - 端口: 443
3. **目的地**:
   - 协议: HTTP
   - 主机名: `localhost`
   - 端口: 8000
4. **自定义标头** Tab → 创建 → 选 **WebSocket** 模板(无副作用,加上稳妥)
5. 保存

然后浏览器用 `https://media-manager.你的域名` 访问就有 HTTPS 了。

记得回到 docker-compose.yml,**把反代地址加到 CORS_ORIGINS**:

```yaml
CORS_ORIGINS: "http://192.168.1.100:8000,https://media-manager.你的域名"
```

重新 `docker compose up -d` 让配置生效。

---

## 8. 备份策略

唯一需要备份的是 `/volume1/docker/media-manager/data/` 目录,里面是:

- `media_manager.db` — SQLite 数据库(你的所有资源元数据、用户、配置)
- `media_manager.db-wal` / `-shm` — WAL 模式的副文件(也要一起备份)
- `thumbnails/` — 视频缩略图(丢了重新扫描会重新生成,**不备份也行**)

群晖的 **Hyper Backup** 套件加一条任务,把 `/volume1/docker/media-manager/data/` 备到 USB 硬盘 / Cloud 即可。

媒体源文件本身(`/volume1/media`)是只读挂载,我们不动,按你 NAS 自己的备份策略处理。

---

## 9. 常见问题

### Q1: 拉镜像失败 `pull access denied`

镜像应该是公开的。如果还是失败:

```bash
# 试一下手动拉看具体错误
sudo docker pull ghcr.io/boylengit/media-manager:latest
```

如果是网络问题(NAS 访问不到 ghcr.io),可以走代理或者用国内 docker mirror。

### Q2: 容器起来了但 8000 端口访问不到

群晖防火墙可能拦了:

1. **控制面板** → **安全性** → **防火墙**
2. 找到当前生效的规则集(默认是 `default`)
3. 编辑规则 → 创建 → 端口选 8000 → 允许

### Q3: 资源库扫不到东西 / 缩略图全是字母占位符

99% 是文件权限问题,容器里的用户读不到 `/volume1/media` 下的文件。

解决:
1. SSH 进 NAS,`id` 查你 NAS 用户的 UID:GID
2. 改 docker-compose.yml 的 `user: "你查到的 UID:GID"`
3. 重新部署

### Q4: 想换端口

把 docker-compose.yml 里的 `"8000:8000"` 改成 `"8090:8000"`(左边是宿主机端口,右边容器内不用改)。同时 `CORS_ORIGINS` 也要跟着改。

### Q5: 升级后界面还是旧版

浏览器强制刷新 `Cmd/Ctrl + Shift + R`(清缓存)。如果还不行,看一下后端版本:

```bash
curl http://NAS-IP:8000/api/health
```

`commit` 字段就是当前版本的 git commit short SHA。和 https://github.com/boyLenGit/media-manager/commits/master 对一下就知道是不是真的升上去了。

### Q6: 我从更早的 MediaHub 版本升级过来,数据会丢吗?

**不会**。系统启动时会自动检测旧的 `mediahub.db` 并改名为 `media_manager.db`,所有资源、用户、配置都会保留。看启动日志能看到:

```
Found legacy database data/mediahub.db, renaming to data/media_manager.db
```

如果你担心,部署前手动备份一下 `data/` 目录最稳。

### Q7: 容器重启后又得重新登录?

`localStorage` 里的 token 会保留,但容器重启时 access_token(15 分钟有效)如果过期了,会自动用 refresh_token 续 — 也就是**最多一次登录后能用 7 天**。如果连 refresh 都过期了,会自动跳登录页。

---

## 10. 完整推荐技术栈

如果你打算搭一整套自动化媒体管家,推荐这些容器一起跑:

```
media-manager  :8000    ← 资源库主入口(本项目)
qbittorrent    :8080    ← 下载器
prowlarr       :9696    ← 搜索源代理(更现代,Jackett 替代品)
jellyfin       :8096    ← 媒体服务器(网页播不了的资源用 Jellyfin 转码播放)
watchtower             ← 自动更新(本文档第 5 节)
```

每个组件都用独立的 docker-compose.yml,方便管理。Prowlarr 配置参考 `docs/tutorials/jackett-prowlarr_cn.md`。

---

## 总结流程图

```
你 git push → GitHub Actions 构建 → ghcr.io 镜像更新
                                        ↓
                              Watchtower 凌晨 4 点拉
                                        ↓
                              media-manager 容器自动重启 (数据保留)
                                        ↓
                              你浏览器访问 → 看到新版
```

部署完成后**完全无需运维**。只要你写代码 push 到 GitHub,NAS 上的服务每天会自动跟进最新版。

如果你想固定版本(避免半夜被自动升级打扰),把 docker-compose.yml 里的 `image:` 行改成具体版本,比如:

```yaml
image: ghcr.io/boylengit/media-manager:sha-3e829a5
```

可用 tag 列表: https://github.com/boyLenGit/media-manager/pkgs/container/media-manager
