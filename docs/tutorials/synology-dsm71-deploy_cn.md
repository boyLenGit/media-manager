# 群晖 DSM 7.1 老版 Docker 部署 Media Manager 实战

> 本文档记录在 **DSM 7.1.x + Docker 套件 20.10.3**(即 DSM 7.2 之前那种"老 Docker 套件",不是 Container Manager)上从零部署 Media Manager 的真实过程。
>
> 包含遇到的所有坑和解决办法。如果你 NAS 是 DSM 7.2+ 自带 Container Manager,请用 [synology-deploy_cn.md](./synology-deploy_cn.md) 那一套更简单的流程。
>
> **关键差异**:
> - DSM 7.1 的 Docker 套件版本太老(20.10.3,2021 年初),**不识别现代 OCI image index 格式的多架构镜像清单**
> - `docker pull ghcr.io/...` 会卡死或下载慢到不可用
> - `docker compose v2` 命令不存在,只有老的 `docker-compose v1`
> - 没有"项目"图形界面(那是 7.2 的 Container Manager 才有)

---

## 0. 适用范围

| 项 | 要求 |
|---|---|
| DSM 版本 | 7.1.x(已在 7.1.1-42962 验证) |
| Docker 套件 | 20.10.x(DSM 7.1 默认就是,套件中心装好即可) |
| 是否需要 root | 部分操作需要 sudo,**bo 用户必须在 administrators 组** |
| 网络要求 | NAS 能访问外网即可,**不需要**配代理(本流程绕开了 docker pull) |

如果你是 7.2+ 用 Container Manager,本文档第 4 章后面的 `pull-image.py + docker load` 部分**仍然有用**(国内拉 ghcr.io 慢的问题永远存在),但前面的"启动方式"可以更简单。

---

## 1. 准备阶段(读了再动手)

### 1.1 必要信息

部署前在本子上记下:

| 信息 | 怎么查 | 例子 |
|---|---|---|
| **NAS 内网 IP** | DSM 控制面板 → 网络 | `192.168.x.xxx` |
| **NAS SSH 端口** | DSM 控制面板 → 终端机 → 启用 SSH 时设置 | `4999` 或自定义 |
| **NAS 管理员账号** | 你的 admin 用户名 | 如 `bo` (任意用户名) |
| **你的用户 UID:GID** | SSH 后执行 `id`,记下两个数字 | `1027:100` |
| **NAS 主用户 UID:GID** | 视频文件归属的用户 | `1026:100` |
| **视频目录** | File Station 看你视频在哪 | `/volume1/xxx/影视` |
| **WebUI 端口** | 你想给 Media Manager 用的端口 | `10001` |

### 1.2 SSH 准备

如果还没启用 SSH:

1. DSM 控制面板 → 终端机和 SNMP → **启用 SSH 服务**
2. 端口建议改成非默认(如 4999),避免被扫描
3. 开启后从你 Mac/Win 试连一次:
   ```bash
   ssh -p 4999 <你的SSH用户名>@<NAS-IP>
   ```
   能进就 OK。

### 1.3 关于"两个用户"的取舍

群晖常见有两种用户:
- **主用户**(假设叫 `youruser`,UID 1026):你日常用的,所有文件归它
- **辅助用户**(如 `bo` (任意用户名),UID 1027):你给容器/SSH 用的临时账号

**容器跑哪个用户?** 推荐用**主用户的 UID:GID**(本例 `1026:100`),原因:
- 视频文件 owner 是主用户,容器要写元数据/缩略图(到 `/volume1/docker/.../data/`)如果用错用户,可能权限错
- 主用户必须在 `users` 组(GID 100),容器读视频靠组权限

SSH 用辅助用户(`bo`)是没问题的,**容器内部跑主用户的 UID:GID** 才是关键。

---

## 2. 第一步:确认 NAS 环境

SSH 进 NAS 后,跑这段脚本探测环境:

```bash
ssh -p 4999 <你的SSH用户名>@<NAS-IP>

# 一气呵成的探测脚本
echo "==== DSM 版本 ===="
cat /etc.defaults/VERSION | grep -E 'productversion|buildnumber'

echo "==== Docker 套件位置 ===="
ls /var/packages/Docker/target/usr/bin/ | grep -E '^(docker|docker-compose)$'

echo "==== Docker 版本 ===="
sudo /var/packages/Docker/target/usr/bin/docker --version
sudo /var/packages/Docker/target/usr/bin/docker-compose --version

echo "==== Docker daemon 是否在跑 ===="
ps -ef | grep -E 'dockerd' | grep -v grep | head -2

echo "==== 我的身份 ===="
id

echo "==== 主用户的身份 ===="
id youruser   # 改成你 NAS 主用户名

echo "==== 视频目录 owner ===="
ls -lan /volume1/xxx/ | grep 影视   # 改成你实际路径
```

**关键观察**:
- DSM `7.1.x` ✅
- `docker --version` 应该是 `Docker version 20.10.x`
- `docker-compose --version` 应该是 `1.28.x` 或类似(v1 老版)
- **没有 `docker compose v2`**(这就是后面用 `docker-compose` 而不是 `docker compose` 的原因)

---

## 3. 第二步:写 docker-compose.yml

### 3.1 创建项目目录

```bash
sudo mkdir -p /volume1/docker/media-manager/data
sudo chown <UID>:<GID> /volume1/docker/media-manager/data   # 改成你主用户的 UID:GID
```

### 3.2 生成 JWT_SECRET

```bash
JWT=$(openssl rand -hex 32)
echo "记下 JWT_SECRET (不要发给任何人): $JWT"
```

记一下这个 64 字符的 hex 串,等会儿要写到 yml 里。

### 3.3 写 docker-compose.yml

⚠️ **下面 4 处带 ⚠️ 的字段必改**:

```bash
sudo tee /volume1/docker/media-manager/docker-compose.yml > /dev/null <<'YAML'
services:
  media-manager:
    image: ghcr.io/boylengit/media-manager:latest
    container_name: media-manager
    restart: unless-stopped
    ports:
      - "10001:8000"          # ⚠️ 左边改成你想用的对外端口
    environment:
      JWT_SECRET: "把这一长串换成你 openssl 生成的 64 字符"   # ⚠️ 必改
      JWT_ACCESS_TTL_MINUTES: 15
      JWT_REFRESH_TTL_DAYS: 7
      CORS_ORIGINS: "http://192.168.x.xxx:10001"             # ⚠️ 改成你 NAS IP + 端口
      TZ: Asia/Shanghai
    volumes:
      - /volume1/docker/media-manager/data:/app/backend/data
      - "/volume1/xxx/影视:/media:ro"                         # ⚠️ 左边改成你视频实际路径
    user: "1026:100"          # ⚠️ 改成你主用户的 UID:GID
    labels:
      - "com.centurylinklabs.watchtower.enable=true"
YAML
```

**4 处必改总结**:
1. 端口 `10001:8000` 左边
2. `JWT_SECRET` 换成 openssl 生成的
3. `CORS_ORIGINS` 改成你 NAS IP
4. 视频路径 + `user` UID:GID

---

## 4. 第三步:获取镜像(避开 docker pull 卡死的坑)

### 4.1 ⚠️ 直接 docker pull 不能用!

DSM 7.1 的 Docker 20.10.3 **不识别 GitHub Container Registry 推的现代 OCI image index 格式**,会出现:

```
❯ sudo docker-compose pull
Pulling media-manager ...
xxx: Pulling fs layer
yyy: Waiting
... (永远卡住或下载几个 layer 后断开)
```

进程不会报错但永远拉不完。

### 4.2 解决方案 A:在另一台能直连 ghcr.io 的机器上下镜像 → scp 过来

**这是本文档实战采用的方案**。

**优点**:
- 不需要重启 NAS 的 dockerd,**不影响其他容器**
- 不需要给 dockerd 配代理
- 通用 — 即使你 NAS 完全访问不了外网,这套也能用

**前置**:你需要一台能正常拉 ghcr.io 的机器(Mac / 公司电脑 / 任何安装了 Python 3 的机器)。

#### 4.2.1 在外部机器下载镜像 → 打包成 tar

不需要装 docker / skopeo,纯 Python 即可。脚本已放在仓库 [`docs/scripts/pull-image.py`](../scripts/pull-image.py),直接下载使用:

```bash
# 在你外部机器上 (Mac/PC/能访问 ghcr.io 的任意机器)
curl -O https://raw.githubusercontent.com/boyLenGit/media-manager/master/docs/scripts/pull-image.py
# 或者从 git clone 的本地仓库直接拷过来

python3 pull-image.py ghcr.io/boylengit/media-manager:latest /tmp/mm-amd64.tar amd64
```

**预期输出**:200MB+ 的 tar 文件,大约 1-3 分钟完成(取决于你外部机器到 ghcr.io 的速度)。

> **脚本原理**:不依赖任何 Docker 客户端,直接用 Python stdlib 走 Registry HTTP API V2:
> 1. 拿匿名 token(Public 镜像不需要登录)
> 2. 拉 manifest(自动处理多架构 image index)
> 3. 并发下载 layer(3 线程)
> 4. 按 docker load 期望的格式打包成 tar
>
> 完整源码见 `docs/scripts/pull-image.py`,80 行 Python。

#### 4.2.2 上传到 NAS

```bash
# 注意 -O 标志!DSM 7.1 的 OpenSSH 不支持新的 sftp 协议,必须用旧版 scp
scp -O -P 4999 /tmp/mm-amd64.tar <你的SSH用户名>@<NAS-IP>:/tmp/mm-amd64.tar
```

⚠️ **`-O` 不可省**:DSM 7.1 自带 OpenSSH 8.2,不支持 OpenSSH 9.0+ 引入的新 sftp 子系统。新 Mac 的 scp 默认用新协议,会报 `subsystem request failed on channel 0`。`-O` 强制走旧 SCP 协议解决。

局域网 1Gbps 下 200MB 大约 16-30 秒。

#### 4.2.3 NAS 上 docker load

回到 NAS SSH 会话:

```bash
DOCKER=/var/packages/Docker/target/usr/bin/docker
sudo $DOCKER load -i /tmp/mm-amd64.tar
# 输出: Loaded image: ghcr.io/boylengit/media-manager:latest

sudo $DOCKER images | grep media-manager
# 应该看到镜像

rm /tmp/mm-amd64.tar       # 清理
```

### 4.3 解决方案 B(可选):配置 dockerd 走 Clash 代理

如果你不想搞外部机器拉 + scp,可以让 NAS 的 dockerd 走代理直接 pull。**代价是要重启 dockerd,所有容器停 1-2 分钟**。

```bash
# 1. 写 systemd override
sudo mkdir -p /etc/systemd/system/pkg-Docker-dockerd.service.d/
sudo tee /etc/systemd/system/pkg-Docker-dockerd.service.d/http-proxy.conf > /dev/null <<'EOF'
[Service]
Environment="HTTPS_PROXY=http://你的代理IP:代理端口"
Environment="HTTP_PROXY=http://你的代理IP:代理端口"
Environment="NO_PROXY=localhost,127.0.0.1,192.168.0.0/16,10.0.0.0/8"
EOF

# 2. 重启 dockerd (⚠️ 影响所有容器!)
sudo systemctl daemon-reload
sudo systemctl restart pkg-Docker-dockerd

# 3. 等 30 秒让 dockerd 起来 + 恢复其他容器
sleep 30

# 4. 现在可以 pull 了
cd /volume1/docker/media-manager
sudo /var/packages/Docker/target/usr/bin/docker-compose pull
```

**风险**:
- 没设 `restart` 策略的容器不会自动起来,需要手动 `docker start <name>`
- Clash 容器自己也会重启,30-60 秒内 NAS 出公网受影响
- 如果代理服务挂了,以后所有 docker pull 都挂

⚠️ **建议先用方案 A**,实在不行再考虑方案 B。

---

## 5. 第四步:启动容器

```bash
DC=/var/packages/Docker/target/usr/bin/docker-compose
cd /volume1/docker/media-manager

sudo $DC up -d

# 等 8 秒看启动日志确认正常
sleep 8
sudo $DC logs --tail 40
```

**期望日志**:

```
media-manager | INFO  Starting Media Manager (debug=False)
media-manager | INFO  Found 4 pending migrations.
media-manager | INFO  Applying migration: 0001_init
media-manager | INFO  Applying migration: 0002_seed
media-manager | INFO  Applying migration: 0003_auth
media-manager | INFO  Applying migration: 0004_rebrand
media-manager | INFO  ffprobe found: /usr/bin/ffprobe
media-manager | INFO  ffmpeg found: /usr/bin/ffmpeg
media-manager | INFO  scan worker started
media-manager | INFO  Application startup complete.
media-manager | INFO  Uvicorn running on http://0.0.0.0:8000
```

看到 `Uvicorn running on...` = 启动成功。

---

## 6. 第五步:验证

### 6.1 命令行验证

```bash
# 容器状态
sudo /var/packages/Docker/target/usr/bin/docker ps | grep media-manager
# 期望: Up xx seconds (health: starting/healthy)  0.0.0.0:10001->8000/tcp

# 健康检查接口
curl -s http://192.168.x.xxx:10001/api/health | python3 -m json.tool
# 期望: {"status": "ok", "version": "...", "commit": "..."}

# 应用信息
curl -s http://192.168.x.xxx:10001/api/info | python3 -m json.tool
# 期望: {"app_name": "Media Manager", ...}

# 是否首次启动
curl -s http://192.168.x.xxx:10001/api/auth/setup-required
# 期望: {"setup_required": true}
```

### 6.2 浏览器验证

打开:
```
http://192.168.x.xxx:10001
```

会自动跳转到「**欢迎使用 Media Manager**」引导页:

1. 输入用户名 + 密码,创建管理员
2. 登录后 → **设置 → 扫描路径 → 添加路径**:
   - **路径**: `/media`(⚠️ 不是 `/volume1/xxx/影视`!容器内只看到 `/media`)
   - **名称**: 任意,如「影视库」
   - **递归**: ✅
   - **启用**: ✅
3. 保存后点该行的 **扫描** 按钮
4. 等几分钟(看你视频数量)
5. 「资源库」页面看到所有视频卡片

---

## 7. 维护命令速查

```bash
# 别名(放到你的 ~/.profile 里方便)
alias d='sudo /var/packages/Docker/target/usr/bin/docker'
alias dc='sudo /var/packages/Docker/target/usr/bin/docker-compose'

# 看容器状态
d ps | grep media-manager

# 跟实时日志
d logs media-manager -f --tail 100

# 重启容器(改了 docker-compose.yml 后)
cd /volume1/docker/media-manager && dc up -d

# 完全停止
cd /volume1/docker/media-manager && dc down

# 看后端版本
curl -s http://192.168.x.xxx:10001/api/health | python3 -m json.tool
# 看 commit 字段,对照 GitHub 的 commit 列表确认是哪一版
```

### 升级到新版本

```bash
# 1. 在外部机器拉新镜像
python3 pull-image.py ghcr.io/boylengit/media-manager:latest /tmp/mm-amd64.tar amd64

# 2. scp 到 NAS
scp -O -P 4999 /tmp/mm-amd64.tar <你的SSH用户名>@<NAS-IP>:/tmp/mm-amd64.tar

# 3. NAS 上 load + 重启
ssh -p 4999 <你的SSH用户名>@<NAS-IP>
sudo /var/packages/Docker/target/usr/bin/docker load -i /tmp/mm-amd64.tar
cd /volume1/docker/media-manager
sudo /var/packages/Docker/target/usr/bin/docker-compose up -d

# 4. 清理
rm /tmp/mm-amd64.tar
```

数据(`/volume1/docker/media-manager/data/`)不会丢。

---

## 8. 备份策略

唯一需要备份的目录:

```
/volume1/docker/media-manager/data/
├── media_manager.db          ← SQLite 数据库 (用户/资源/标签/配置)
├── media_manager.db-wal      ← WAL 副文件
├── media_manager.db-shm      ← SHM 副文件
└── thumbnails/               ← 缩略图(丢了重扫即可)
```

用 **Hyper Backup** 套件:

1. 数据备份任务 → 新增
2. 数据源勾选 `/volume1/docker/media-manager/data/`
3. 调度:每天凌晨 1 点
4. 备份目标:USB 硬盘 / 远端 NAS / Synology C2 / OneDrive 等

媒体源文件本身(`/volume1/xxx/影视`)是只读挂载,**Media Manager 从不修改**,按你 NAS 自己的备份策略处理即可。

---

## 9. 实战中遇到的坑(以后不踩)

### 坑 1:`docker pull` 卡住不报错

**症状**:
```
sudo docker-compose pull
Pulling media-manager ...
xxx: Pulling fs layer
... (永远卡住或只下几个 layer 就停)
```

**根因**:Docker 20.10.3 不识别 OCI image index v1 格式(`application/vnd.oci.image.index.v1+json`),GitHub Actions buildx 构建的多架构镜像默认就是这个格式。

**解决**:
- **服务端方案**:CI workflow 加 `outputs: type=registry,manifest:type=docker`,推旧 Docker manifest list v2 格式(已修复,见 `.github/workflows/docker-publish.yml`)
- **客户端方案**:本文档第 4 章的 `pull-image.py` 跳过 docker pull,直接走 Registry HTTP API

### 坑 2:`scp` 报 `subsystem request failed on channel 0`

**症状**:
```
$ scp -P 4999 file.tar <user>@<nas-ip>:/tmp/
subsystem request failed on channel 0
scp: Connection closed
```

**根因**:OpenSSH 9.0+ 客户端默认用 SFTP 协议传输,DSM 7.1 自带的 OpenSSH 8.2 不支持。

**解决**:加 `-O` 标志强制用旧 SCP 协议:
```bash
scp -O -P 4999 file.tar <user>@<nas-ip>:/tmp/
```

### 坑 3:`docker compose v2` 命令不存在

**症状**:
```
$ sudo docker compose up -d
docker: 'compose' is not a docker command.
```

**根因**:DSM 7.1 的 Docker 套件只有 `docker-compose v1`(独立的二进制),没集成 `docker compose v2` 子命令。

**解决**:命令一律用 `docker-compose`(中间是连字符):
```bash
sudo /var/packages/Docker/target/usr/bin/docker-compose up -d
```

### 坑 4:`docker` 命令找不到

**症状**:
```
$ docker --version
sh: docker: command not found
```

**根因**:DSM 把 Docker 套件装在 `/var/packages/Docker/target/usr/bin/`,普通用户的 PATH 没包含。

**解决**:用全路径,或者把它加到 PATH:
```bash
# 加到 ~/.profile 永久生效
export PATH="/var/packages/Docker/target/usr/bin:$PATH"
```

### 坑 5:容器扫不到视频文件 / 缩略图全是字母占位符

**根因**:容器内的 user 跟 NAS 上视频文件的 owner 不一致,读不到文件。

**诊断**:
```bash
# 看视频文件 owner
ls -lan /volume1/xxx/影视/ | head -3
# 假设 owner 是 1026:100

# 看 docker-compose.yml 里的 user
grep 'user:' /volume1/docker/media-manager/docker-compose.yml
# 应该跟视频 owner 匹配
```

**解决**:把 docker-compose.yml 里 `user: "1026:100"` 改成跟视频 owner 一致,然后:
```bash
cd /volume1/docker/media-manager
sudo docker-compose up -d
```

### 坑 6:`rm` 卡顿 / SSH 命令偶尔超时

**根因**:DSM 上一些命令(尤其是非 GNU 版本)行为跟 Linux 不一样,例如:
- `pgrep` 不存在
- `ps -ef | awk` 是稳的,但 `ps aux` 输出格式不一样
- `pkill` 偶尔会卡住或行为异常

**解决**:用更通用的写法,例如:
```bash
# 不要用 pgrep
PIDS=$(ps -ef | grep "docker pull" | grep -v grep | awk '{print $2}')
[ -n "$PIDS" ] && sudo kill -9 $PIDS
```

---

## 10. 完整一键部署脚本(给熟手)

把所有步骤合并成一个脚本,改 4 处变量即可:

```bash
#!/bin/bash
# 在 NAS 上跑这个脚本(已经 SSH 进去了)
set -e

# ============================
# 改这 5 个变量
# ============================
NAS_IP="192.168.x.xxx"
WEBUI_PORT="10001"
NAS_USER_UID_GID="1026:100"          # 主用户的 id 输出
MEDIA_DIR="/volume1/xxx/影视"
PROJ_DIR="/volume1/docker/media-manager"

# ============================
# 自动部分
# ============================
DOCKER=/var/packages/Docker/target/usr/bin/docker
DC=/var/packages/Docker/target/usr/bin/docker-compose

# 1. 准备目录
sudo mkdir -p "$PROJ_DIR/data"
sudo chown ${NAS_USER_UID_GID%:*}:${NAS_USER_UID_GID#*:} "$PROJ_DIR/data"

# 2. 写 docker-compose.yml
JWT=$(openssl rand -hex 32)
echo "JWT_SECRET (备份这个): $JWT"

sudo tee "$PROJ_DIR/docker-compose.yml" > /dev/null <<EOF
services:
  media-manager:
    image: ghcr.io/boylengit/media-manager:latest
    container_name: media-manager
    restart: unless-stopped
    ports:
      - "$WEBUI_PORT:8000"
    environment:
      JWT_SECRET: "$JWT"
      JWT_ACCESS_TTL_MINUTES: 15
      JWT_REFRESH_TTL_DAYS: 7
      CORS_ORIGINS: "http://$NAS_IP:$WEBUI_PORT"
      TZ: Asia/Shanghai
    volumes:
      - $PROJ_DIR/data:/app/backend/data
      - "$MEDIA_DIR:/media:ro"
    user: "$NAS_USER_UID_GID"
    labels:
      - "com.centurylinklabs.watchtower.enable=true"
EOF

echo "compose 文件已写入。"

# 3. 提示拉镜像
cat <<HINT

⚠️ 接下来:
1. 在外部能访问 ghcr.io 的机器上跑:
     python3 pull-image.py ghcr.io/boylengit/media-manager:latest /tmp/mm-amd64.tar amd64
2. scp 到 NAS:
     scp -O -P 4999 /tmp/mm-amd64.tar <user>@$NAS_IP:/tmp/mm-amd64.tar
3. 回到 NAS 跑:
     sudo $DOCKER load -i /tmp/mm-amd64.tar
     cd $PROJ_DIR && sudo $DC up -d
HINT
```

---

## 11. 常见问题速查

### Q: 怎么看哪些容器在跑?
```bash
sudo /var/packages/Docker/target/usr/bin/docker ps
```

### Q: 容器起不来,怎么诊断?
```bash
sudo /var/packages/Docker/target/usr/bin/docker-compose -f /volume1/docker/media-manager/docker-compose.yml logs --tail 100
```

### Q: 改 docker-compose.yml 后怎么应用?
```bash
cd /volume1/docker/media-manager
sudo /var/packages/Docker/target/usr/bin/docker-compose up -d
# 它会检测变化,只重启需要重启的服务
```

### Q: 完全卸载?
```bash
cd /volume1/docker/media-manager
sudo /var/packages/Docker/target/usr/bin/docker-compose down
sudo rm -rf /volume1/docker/media-manager/   # ⚠️ 会丢失数据!
sudo /var/packages/Docker/target/usr/bin/docker rmi ghcr.io/boylengit/media-manager:latest
```

### Q: 数据库迁移会不会丢数据?
**不会**。Media Manager 启动时会自动应用 SQL migrations 到 SQLite,但所有 schema 改动都是 **ADD COLUMN / ALTER** 类型,不删既有数据。如果你担心,升级前手动备份 `data/` 目录即可。

### Q: 浏览器访问 8000 / 10001 端口连不上?
1. 防火墙:DSM 控制面板 → 安全性 → 防火墙 → 加规则放行
2. 端口冲突:`sudo ss -tlnp | grep 10001` 看是否被占用
3. 容器没起:`sudo docker ps` 看 STATUS 是不是 Up

---

## 12. 升级到 DSM 7.2 后的迁移

如果你以后升级 DSM 到 7.2+(自带 Container Manager,Docker 版本会自动升到 24+),**本文档的 `pull-image.py` 流程仍然有用**(国内拉 ghcr.io 慢的问题不会因 DSM 升级而消失),但你也可以改用 [synology-deploy_cn.md](./synology-deploy_cn.md) 的 Container Manager 图形化方式。

迁移步骤(数据完整保留):
1. 升级 DSM 到 7.2(套件中心会自动升级 Docker → Container Manager)
2. **不用动**任何容器,Container Manager 会自动接管现有的 docker-compose.yml
3. 验证:打开 Container Manager → 项目 → 应该能看到 `media-manager` 项目
4. 之后正常用图形界面或 SSH 都可以
