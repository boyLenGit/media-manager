# 群晖 DSM 7.1 老 Docker 更新 Media Manager 教程

> 本文是 [synology-dsm71-deploy_cn.md](./synology-dsm71-deploy_cn.md) 的姊妹篇 — 部署完成后,以后**怎么更新到新版本**?
>
> **核心结论**:不复杂,但有 3 种方式可选,每种适合不同场景。

---

## 0. 更新前你需要知道的

### 数据安全保证

**更新永远不会丢数据。** 因为:

- 你的数据(SQLite 数据库 / 缩略图 / 用户 / 标签 / 配置)全部存在 `/volume1/docker/media-manager/data/` 目录
- 这个目录是**绑定挂载**到容器里的(docker-compose.yml 的 `volumes:` 配置),**跟容器寿命无关**
- 哪怕容器被删了重建,挂卷的数据完整保留
- 即使新版镜像启动失败,旧数据**没动过**,改 image tag 一键回滚

数据库 schema 升级也是**幂等的、向前兼容的**(只 ADD COLUMN,不删除字段),Media Manager 启动时自动跑 migration,旧数据保留。

### 何时需要更新?

- GitHub 仓库有新的 `master` 分支提交(可在 https://github.com/boyLenGit/media-manager/commits/master 看)
- CI 跑完会自动推一个新的 `:latest` 镜像到 ghcr.io
- 你 NAS 上的 Media Manager 当前版本可以这样查:

  ```bash
  curl -s http://你的NAS-IP:10001/api/health | python3 -m json.tool
  # 返回 {"commit": "1390f51..."}
  ```

  把这个 commit 短 SHA 跟 GitHub 最新 commit 对比,如果落后就可以更新。

---

## 1. 三种更新方案对比

| 方案 | 操作复杂度 | 速度 | 适合 |
|---|---|---|---|
| **A. 一键脚本** | 1 行命令 | 慢(国内拉 ghcr 通常 5-10 分钟) | 平时升级、不急 |
| **B. 手动 docker-compose** | 3 行命令 | 同 A | 需要手工控制每一步 |
| **C. 外部机器拉镜像 + scp** | 3 段命令(2 端配合) | **快(2-5 分钟)** | 急用 / docker pull 卡死了 |

**我的建议**:
- 平时用方案 A(一键脚本),省事
- 如果脚本卡住超过 15 分钟,Ctrl+C 中断,转用方案 C
- 想了解每一步在干啥,看方案 B

---

## 2. 方案 A:一键脚本(推荐)

### 2.1 第一次部署脚本

把仓库的 [`docs/scripts/update-on-synology.sh`](../scripts/update-on-synology.sh) 复制到 NAS 上:

```bash
# 一种简单做法:在外部机器上 clone 仓库后 scp 上去
scp -O -P <SSH端口> docs/scripts/update-on-synology.sh \
    <你的用户>@<NAS-IP>:/volume1/docker/media-manager/update.sh

# 或在 NAS 上 wget 下来
ssh -p <SSH端口> <你的用户>@<NAS-IP>
cd /volume1/docker/media-manager
wget https://raw.githubusercontent.com/boyLenGit/media-manager/master/docs/scripts/update-on-synology.sh -O update.sh
chmod +x update.sh
```

### 2.2 以后每次更新

```bash
ssh -p <SSH端口> <你的用户>@<NAS-IP>
cd /volume1/docker/media-manager
./update.sh
```

脚本会自动:

1. 记录当前版本(用于失败时回滚)
2. 拉最新镜像 (`docker-compose pull`)
3. 重新创建容器 (`docker-compose up -d`)
4. 等健康检查通过(最多 60 秒)
5. 清理 dangling 旧镜像
6. 输出 "old → new" 版本对比

### 2.3 脚本会输出什么

正常情况:

```
[14:23:01] ==== 1/4 记录当前版本 (用于失败回滚) ====
  ✓ 当前 image ID: 17b0993e4280
  ✓ 当前版本 commit: 7282cf3
[14:23:02] ==== 2/4 拉取最新镜像 ====
  这一步可能很慢 (国内拉 ghcr.io 通常 5-10 分钟)
  如果超过 15 分钟没动,Ctrl+C 中断,改用方案 C(外部机器拉)
Pulling media-manager ... done
  ✓ 镜像拉取完成
[14:28:35] ==== 3/4 重新创建容器 ====
Recreating media-manager ... done
  ✓ 容器已重启
[14:28:38] ==== 4/4 等待健康检查并清理旧镜像 ====
  健康检查 ............ ✓
  ✓ 新版本上线: 1390f51
  ✓ 已清理 dangling 旧镜像
[14:28:55] ==== 完成 ====

[14:28:55] ✓ 升级成功: 7282cf3 → 1390f51

[14:28:55] 浏览器刷新一下页面 (Ctrl+Shift+R / Cmd+Shift+R) 看到新前端
```

### 2.4 升级后端必看:刷新浏览器缓存

后端版本号 (`commit`) 是更新了,但**浏览器可能还在用旧的 JS/CSS**。强制刷新:

| 系统 | 快捷键 |
|---|---|
| Mac | `Cmd + Shift + R` |
| Windows / Linux | `Ctrl + Shift + R` |

---

## 3. 方案 B:手动 docker-compose

如果你想知道脚本到底在干啥,或者想拆开做:

```bash
ssh -p <SSH端口> <你的用户>@<NAS-IP>

# 用全路径(普通用户的 PATH 没包含 Docker 套件位置)
DC=/var/packages/Docker/target/usr/bin/docker-compose
cd /volume1/docker/media-manager

# 1. 拉新镜像 (Docker 会对比 manifest digest,只下载变动的 layer)
sudo $DC pull

# 2. 用新镜像重新创建容器
#    docker-compose 会发现 image 变了,自动:停旧容器 → 用新镜像启动 → 同样的 volumes/env/network
sudo $DC up -d

# 3. (可选) 清理旧镜像 (只清理被顶替没人引用的,不影响运行中的容器)
sudo /var/packages/Docker/target/usr/bin/docker image prune -f

# 4. 看日志确认启动成功
sudo $DC logs --tail 30 media-manager

# 5. 验证版本
curl -s http://你的NAS-IP:10001/api/health | python3 -m json.tool
```

---

## 4. 方案 C:外部机器拉镜像 + scp 到 NAS(快速)

### 何时用这种?

- 方案 A/B 卡了超过 15 分钟没进度
- 国内拉 ghcr.io 速度奇慢 / 直接报 timeout
- 你急着用

### 4.1 外部机器(Mac/能直连 ghcr.io 的电脑)

```bash
# 把仓库脚本拷到本地
git clone https://github.com/boyLenGit/media-manager.git
cd media-manager

# 拉镜像 → 打包成 tar (200MB+,1-3 分钟)
python3 docs/scripts/pull-image.py \
    ghcr.io/boylengit/media-manager:latest \
    /tmp/mm-amd64.tar amd64
```

输出会显示进度:

```
1. 获取 token
2. 获取 manifest
3. 镜像有 13 层
4. 下载 config
5. 并发下载 13 个 layer (3 并发)
   [1/13] sha256:5b4d6ff92fc4... (28.6 MB)
      下载 5 / 28 MB
      下载 10 / 28 MB
      ...
6. 打包到 /tmp/mm-amd64.tar
   完成: /tmp/mm-amd64.tar (229 MB)
7. ✓ 全部完成
```

### 4.2 上传到 NAS

```bash
# ⚠️ -O 标志不能省 (DSM 7.1 OpenSSH 8.2 不支持新 sftp 协议)
scp -O -P <SSH端口> /tmp/mm-amd64.tar \
    <你的用户>@<NAS-IP>:/tmp/mm-amd64.tar
```

局域网 1Gbps 下,200MB 大约 15-30 秒。

### 4.3 NAS 上 load + 重启

```bash
ssh -p <SSH端口> <你的用户>@<NAS-IP>

DOCKER=/var/packages/Docker/target/usr/bin/docker
DC=/var/packages/Docker/target/usr/bin/docker-compose

# 1. load 新镜像 (会顶替同名 :latest tag,但旧镜像 image-id 还在)
sudo $DOCKER load -i /tmp/mm-amd64.tar
# 输出: Loaded image: ghcr.io/boylengit/media-manager:latest

# 2. 用新镜像重新创建容器
cd /volume1/docker/media-manager
sudo $DC up -d
# 输出: Recreating media-manager ... done

# 3. 删 tar 清理
rm /tmp/mm-amd64.tar

# 4. (可选) 清理 dangling 旧镜像
sudo $DOCKER image prune -f

# 5. 验证
curl -s http://你的NAS-IP:10001/api/health | python3 -m json.tool
```

整套流程 2-5 分钟,**比方案 A 快 5 倍以上**(国内场景)。

---

## 5. 常见问题

### Q1: 我的 docker-compose.yml 改过本地内容,更新会被覆盖吗?

**不会**。docker-compose pull 只拉镜像,**不动你的 yml 文件**。你改过的 ports / volumes / env 都保留。

但要注意:**如果新版本添加了新环境变量**(比如某个新功能需要),你需要手工把它加进 yml,否则该功能不会启用。我会在 commit message 里说明这种破坏性变更。

### Q2: 浏览器刷新后还是旧的 UI

强制刷新 (`Cmd/Ctrl + Shift + R`) 清缓存。如果还不行,看后端 commit 是不是真升了:

```bash
curl http://你的NAS-IP:10001/api/health
# {"commit": "..."}
```

把这个 commit 短 SHA 跟 GitHub 上最新 commit 对一下。如果不一致,说明镜像没真的升级,docker-compose 可能用的是缓存。强制重建:

```bash
cd /volume1/docker/media-manager
sudo docker-compose pull
sudo docker-compose up -d --force-recreate
```

### Q3: 升级后报错,容器起不来

**看日志**:

```bash
cd /volume1/docker/media-manager
sudo docker-compose logs --tail 100 media-manager
```

最常见原因:
- **数据库 migration 失败**(我们尽量避免,但不排除新版本有 schema 不兼容 bug)
  → 先备份 `data/`,然后看具体错误
- **新版本要求新环境变量但 yml 没加**
  → 看 commit message,补到 yml 里
- **新版本依赖系统包问题**
  → 几乎不会,因为 ffmpeg 等都打到镜像里

### Q4: 怎么回滚到旧版本?

#### 方法 A:你之前用过 update.sh,旧 image-id 还在

```bash
# 看 image 列表,找你想回滚的 IMAGE ID
sudo docker images | grep media-manager
# 例如:
# ghcr.io/boylengit/media-manager   latest    1390f51...   2 hours ago
# <none>                            <none>    7282cf3...   1 day ago

# 改 yml 里的 image (把 :latest 换成具体 image-id 或 sha-xxxxxx tag)
nano /volume1/docker/media-manager/docker-compose.yml
# image: ghcr.io/boylengit/media-manager:sha-7282cf3

# 重启
sudo docker-compose up -d
```

#### 方法 B:用 ghcr.io 上具体 commit tag

每次 CI 都会推 `sha-xxxxxxx` tag,你可以指定到任意历史版本:

```yaml
# docker-compose.yml
image: ghcr.io/boylengit/media-manager:sha-7282cf3
```

可用 tag 列表:https://github.com/boyLenGit/media-manager/pkgs/container/media-manager

```bash
sudo docker-compose pull
sudo docker-compose up -d
```

### Q5: 一直回滚回滚的不优雅,有没有办法测试新版本?

最稳的做法:**生产容器跑 :sha-xxxxx 固定版本,平时用第二个临时容器测 :latest**。

新建一个 test 项目目录:

```bash
mkdir -p /volume1/docker/media-manager-test/data
cd /volume1/docker/media-manager-test
cat > docker-compose.yml <<EOF
services:
  test:
    image: ghcr.io/boylengit/media-manager:latest
    container_name: media-manager-test
    ports:
      - "10002:8000"          # 用不同端口
    environment:
      JWT_SECRET: "test"      # 测试用,不重要
    volumes:
      - ./data:/app/backend/data
      # 不挂媒体目录,纯测试
EOF
sudo docker-compose up -d
# 访问 http://你的NAS-IP:10002 看新版
```

### Q6: 怎么知道有新版本?

最方便:在 GitHub 仓库点 **Watch → Custom → Releases**(以后我打 tag 会通知)
平时:看 https://github.com/boyLenGit/media-manager/commits/master 有没有新 commit

或者你定时跑(cron 任务):

```bash
# 每周一凌晨 4 点检查并自动更新
0 4 * * 1 /volume1/docker/media-manager/update.sh > /var/log/mm-update.log 2>&1
```

群晖控制面板 → 任务计划 → 新增 → 计划的任务 → 用户定义的脚本,粘上面这条。

### Q7: 自动更新 (Watchtower) 在 7.1 能用吗?

能用。Watchtower 自己也是 docker 容器,加到 docker-compose.yml 即可:

```yaml
services:
  media-manager:
    # ... 你现有配置 ...
    labels:
      - "com.centurylinklabs.watchtower.enable=true"

  watchtower:
    image: containrrr/watchtower
    container_name: watchtower
    restart: unless-stopped
    environment:
      WATCHTOWER_SCHEDULE: "0 0 4 * * *"   # 凌晨 4 点
      WATCHTOWER_LABEL_ENABLE: "true"
      WATCHTOWER_CLEANUP: "true"
      TZ: Asia/Shanghai
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
```

但有个问题:**Watchtower 和 docker pull 一样会受到老 docker manifest 兼容问题影响**。我们的 CI 已经改成推 v2 manifest 格式,理论上能拉,但拉得慢。

**我的建议**:DSM 7.1 不要用 Watchtower 自动更新,容易半夜卡住或失败。手动用 update.sh 更可控。

---

## 6. 速查命令

```bash
# 看当前版本
curl -s http://你的NAS-IP:10001/api/health | python3 -m json.tool

# 看容器状态
sudo /var/packages/Docker/target/usr/bin/docker ps | grep media-manager

# 看实时日志
sudo /var/packages/Docker/target/usr/bin/docker logs media-manager -f --tail 100

# 一键更新 (方案 A)
cd /volume1/docker/media-manager && ./update.sh

# 手动更新 (方案 B)
cd /volume1/docker/media-manager
sudo /var/packages/Docker/target/usr/bin/docker-compose pull
sudo /var/packages/Docker/target/usr/bin/docker-compose up -d

# 查看历史镜像 (用于回滚)
sudo /var/packages/Docker/target/usr/bin/docker images | grep media-manager

# 回滚到具体版本
# 1. 编辑 docker-compose.yml,把 image: 改成 :sha-xxxxxxx
# 2. sudo docker-compose up -d
```

---

## 7. 一图流总结

```
日常更新 (推荐)
    cd /volume1/docker/media-manager && ./update.sh
                        ↓
                 (成功 → 完成)
                        ↓
                 (卡住 > 15min)
                        ↓
            Ctrl+C 中断 → 走方案 C
                        ↓
   外部机器:
      python3 docs/scripts/pull-image.py \
          ghcr.io/boylengit/media-manager:latest \
          /tmp/mm.tar amd64
      scp -O -P <端口> /tmp/mm.tar <用户>@<NAS>:/tmp/mm.tar
                        ↓
   NAS:
      sudo docker load -i /tmp/mm.tar
      cd /volume1/docker/media-manager
      sudo docker-compose up -d
                        ↓
                    完成 ✓
```

---

## 8. 升级到 DSM 7.2 后

如果你以后升级 DSM 到 7.2+(自带 Container Manager,Docker 24+):

- **本文档的方案 A/B 仍然有效**,只是命令路径变了:`docker compose` 替代 `docker-compose`(中间空格而非连字符)
- **方案 C 也仍然有效**,新 docker 客户端依然能 `docker load`
- **可以启用 Watchtower 自动更新**,新 docker 拉 ghcr.io 又快又稳
- 也可以直接在 Container Manager 图形界面点"重启" / "更新"
