# 群晖 NAS 部署 + 自动更新

> 本教程教你把 MediaHub 部署到群晖 NAS,并配置成"git push 后 NAS 自动更新到最新版"的全自动模式。

---

## 0. 整体架构

```
┌─────────────────┐  你 git push  ┌─────────────────┐
│  本地开发机      │ ───────────►  │   GitHub       │
└─────────────────┘                │   仓库          │
                                   └────────┬────────┘
                                            │ 触发
                                            ▼
                                   ┌─────────────────┐
                                   │ GitHub Actions  │
                                   │ docker build    │
                                   │ + push image    │
                                   └────────┬────────┘
                                            │ 推送
                                            ▼
                                   ┌─────────────────┐
                                   │  ghcr.io        │ ← 镜像仓库
                                   │ <镜像>:latest   │
                                   └────────┬────────┘
                                            │ 每天检查
                                            │ pull
                                            ▼
        ┌──────────────────────────────────────────────────┐
        │                你的群晖 NAS                       │
        │                                                  │
        │   ┌────────────┐    ┌──────────┐    ┌─────────┐ │
        │   │ Watchtower │ →  │ MediaHub │    │ 你的    │ │
        │   │  自动更新  │    │  容器    │ ←  │ 浏览器  │ │
        │   └────────────┘    └──────────┘    └─────────┘ │
        └──────────────────────────────────────────────────┘
```

**全流程零干预**:你写代码 → push → 等 5-10 分钟,NAS 上的服务自动升级到新版本。

---

## 1. 前置条件

- 群晖 DSM 7.2+,装了 **Container Manager**(就是新版 Docker)
- NAS 能访问外网(拉镜像和 Watchtower 检查更新需要)
- 一个 GitHub 账号(代码已在 https://github.com/boyLenGit/media-manager)

---

## 2. 第一次部署

### 2.1 准备目录

SSH 进群晖(或在 File Station 里手动建),建一个项目目录:

```bash
ssh admin@nas-ip
cd /volume1/docker      # 或你习惯的位置
mkdir -p mediahub && cd mediahub
mkdir -p data
```

### 2.2 上传两个文件

把这两个文件上传到 `/volume1/docker/mediahub/` 下:

**docker-compose.yml**

```yaml
services:
  mediahub:
    image: ghcr.io/boylengit/media-manager:latest
    container_name: mediahub
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      JWT_SECRET: 你用 openssl rand -hex 32 生成的密钥
      CORS_ORIGINS: http://nas-ip:8000
      TZ: Asia/Shanghai
    volumes:
      - ./data:/app/backend/data
      # 改成你的 NAS 媒体目录,可加多行
      - /volume1/media:/media:ro
      - /volume1/downloads:/downloads:rw
    user: "1026:100"          # ← 改成你 NAS 用户的 UID:GID
    labels:
      - "com.centurylinklabs.watchtower.enable=true"

  watchtower:
    image: containrrr/watchtower
    container_name: watchtower
    restart: unless-stopped
    environment:
      WATCHTOWER_SCHEDULE: "0 0 4 * * *"   # 每天凌晨 4 点检查
      WATCHTOWER_LABEL_ENABLE: "true"
      WATCHTOWER_CLEANUP: "true"
      TZ: Asia/Shanghai
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
```

**怎么找 UID/GID?**

```bash
ssh admin@nas-ip
id admin              # 输出形如 uid=1026(admin) gid=100(users) ...
# 把 user: "1026:100" 改成你看到的数字
```

### 2.3 启动

```bash
cd /volume1/docker/mediahub

# 拉镜像 + 启动
sudo docker compose up -d

# 看日志
sudo docker compose logs -f mediahub
```

第一次启动会下载镜像(约 200 MB),完成后访问:

```
http://<nas-ip>:8000
```

第一次会进入"初始化"页面,创建管理员账号即可。

### 2.4 验证 Watchtower 在跑

```bash
sudo docker logs watchtower
```

应该看到类似:

```
time="2026-01-01T04:00:00+08:00" level=info msg="Session done"
time="2026-01-01T04:00:00+08:00" level=info msg="Watchtower 1.x.x"
```

---

## 3. 用 Container Manager 图形界面部署(更适合不熟 SSH 的)

1. **Container Manager** → **项目** → 点 **新增**
2. 项目名:`mediahub`
3. 路径:`/docker/mediahub`(自动创建)
4. 来源:**创建 docker-compose.yml**,粘贴上面的内容
5. 下一步 → 摘要 → 完成
6. 第一次启动会拉镜像,等几分钟
7. 浏览器打开 `http://nas-ip:8000`

---

## 4. 工作流:你改代码 → NAS 自动更新

### 你这边

```bash
cd /Users/bl/Project/media-manager
# 改代码...
git add -A
git commit -m "feat: xxx"
git push origin master
```

### GitHub 自动做的事

- 触发 `.github/workflows/docker-publish.yml` 这个 Action
- 运行 ~ 5-8 分钟:多架构构建(amd64 + arm64)、推送到 `ghcr.io/boylengit/media-manager:latest`
- 你可以在 https://github.com/boyLenGit/media-manager/actions 看进度

### Watchtower 自动做的事

- 每天凌晨 4 点(可改)检查 ghcr.io 上 `latest` 是不是有新 digest
- 如果有,自动 `docker pull` + 优雅重启容器
- 旧镜像会清理掉(`WATCHTOWER_CLEANUP: true`)

### 你想立即更新一次怎么办?

```bash
ssh admin@nas-ip
cd /volume1/docker/mediahub
sudo docker compose pull && sudo docker compose up -d
```

或者让 Watchtower 立即跑一次:

```bash
sudo docker exec watchtower /watchtower --run-once mediahub
```

---

## 5. 升级 / 回滚

### 想固定版本(避免半夜被自动更新打扰)

把 `docker-compose.yml` 里的 `image:` 行改成具体 tag:

```yaml
image: ghcr.io/boylengit/media-manager:v1.2.3
```

或者用 commit short SHA:

```yaml
image: ghcr.io/boylengit/media-manager:sha-a1b2c3d
```

可用的 tag 列表在:https://github.com/boyLenGit/media-manager/pkgs/container/media-manager

### 回滚到上一个版本

```bash
cd /volume1/docker/mediahub
# 编辑 docker-compose.yml,把 image 改成具体老版本
sudo docker compose pull
sudo docker compose up -d
```

### 发布正式版本(打 tag)

```bash
git tag v1.0.0
git push origin v1.0.0
```

GitHub Actions 检测到 `v*.*.*` tag 会构建带版本号的镜像:

- `ghcr.io/boylengit/media-manager:1.0.0`
- `ghcr.io/boylengit/media-manager:1.0`
- `ghcr.io/boylengit/media-manager:1`
- `ghcr.io/boylengit/media-manager:latest`

---

## 6. 数据备份

唯一需要备份的目录是 `/volume1/docker/mediahub/data/`(SQLite 数据库 + 系统设置)。

群晖 **Hyper Backup** 加这一个目录到任务即可。

媒体文件(`/volume1/media`、`/volume1/downloads`)是只读挂载,不在我们这层维护,正常按你 NAS 自身的备份策略处理。

---

## 7. 反代 + HTTPS(强烈推荐)

直接暴露 8000 端口不安全。建议用群晖的反向代理:

1. **控制面板** → **登录入口** → **高级** → **反向代理服务器** → **新增**
2. 来源:
   - 协议:HTTPS
   - 主机名:`mediahub.your-domain.com` 或 `nas.local`
   - 端口:443
3. 目的地:
   - 协议:HTTP
   - 主机名:localhost
   - 端口:8000
4. **自定义标头** → 新增 → **WebSocket** 模板(虽然我们没用 WS,加上无害)

然后浏览器访问 `https://mediahub.your-domain.com` 即可。

记得**回到 docker-compose.yml** 改 `CORS_ORIGINS` 加上反代地址:

```yaml
CORS_ORIGINS: http://nas-ip:8000,https://mediahub.your-domain.com
```

---

## 8. 常见问题

### Q1: 拉镜像失败 `unauthorized`

仓库还是私有的。两种办法:

- **办法 A(推荐)**:把镜像设为公开 — 打开 https://github.com/boyLenGit/media-manager/pkgs/container/media-manager → **Package settings** → **Change visibility** → **Public** → 输入仓库名确认

- **办法 B**:让 NAS 用 token 登录 ghcr.io
  ```bash
  # 在 NAS 上
  echo "ghp_xxx" | sudo docker login ghcr.io -u boyLenGit --password-stdin
  ```
  然后再 `docker compose pull`

### Q2: 群晖架构不对(arm 错误)

我们的镜像是多架构构建,**amd64 / arm64 都支持**(覆盖 99% 群晖型号)。
万一你是 arm v7 等小众型号,看 `docker info` 输出的 `Architecture`,然后:

```bash
# 临时只看支持的架构
docker manifest inspect ghcr.io/boylengit/media-manager:latest | grep architecture
```

如不支持你的架构,issue 联系我,我加一个 platform 即可。

### Q3: Watchtower 没生效

检查容器有没有打标签:

```bash
sudo docker inspect mediahub | grep -A 2 Labels
# 应该看到 "com.centurylinklabs.watchtower.enable": "true"
```

或者改成"看光所有容器"模式 — 把 watchtower 的 `WATCHTOWER_LABEL_ENABLE` 改成 `false`(危险,会更新所有容器,包括别的服务)。

### Q4: 自动更新后服务挂了 / 数据丢失

不会丢数据,因为 `data/` 是卷挂载、独立于镜像。

如果新版本有 bug 让服务起不来,Watchtower 不会回滚,你需要手动:

```bash
cd /volume1/docker/mediahub
# 改 image 改成上个能跑的版本
sudo docker compose up -d
```

为了避免这种情况,**生产环境建议固定到具体版本号**,不要用 `latest`,Watchtower 也别用。需要更新时手动 `docker compose pull` + `up -d`。

### Q5: 想接收更新通知

Watchtower 支持 Telegram / Slack / 邮件 / 任意 Webhook,在 docker-compose.yml 的 watchtower 服务里加:

```yaml
environment:
  WATCHTOWER_NOTIFICATIONS: shoutrrr
  WATCHTOWER_NOTIFICATION_URL: telegram://<bot-token>@telegram?chats=<chat-id>
```

格式参考:https://containrrr.dev/shoutrrr/

---

## 9. 推荐部署组合

完整 NAS 媒体栈(`indexer-compose.yml` 单独管,避免配置文件太长):

```
docker-compose.yml          → MediaHub + Watchtower + qBittorrent
indexer-compose.yml         → Jackett/Prowlarr (见 jackett-prowlarr_cn.md)
jellyfin-compose.yml        → Jellyfin (可选,网页播不了大文件时的兜底)
```

完整一份在仓库 `docs/examples/full-stack-compose.yml`(待补)。

---

## 10. 检查当前版本

随时可以问后端跑的是哪个版本:

```bash
curl http://nas-ip:8000/api/health
```

返回:

```json
{
  "status": "ok",
  "time": "2026-01-01T00:00:00Z",
  "version": "1.0.0",
  "commit": "a1b2c3d4..."
}
```

如果你看到 `version: dev` 说明是手动 build 的本地镜像。
