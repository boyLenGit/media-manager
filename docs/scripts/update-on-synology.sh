#!/bin/bash
# Media Manager - 群晖 NAS 一键更新脚本
#
# 用法:在 NAS 上 SSH 登录后,把这个脚本放到 /volume1/docker/media-manager/ 下
#       第一次需要 chmod +x update.sh
#       以后每次更新就跑: ./update.sh
#
# 工作原理:
#   1. 拉最新镜像 (docker-compose pull)
#   2. 重新创建容器 (docker-compose up -d)
#   3. 清理旧镜像 (docker image prune -f, 仅清理 dangling 的)
#
# 数据安全:
#   - SQLite 数据库 / 缩略图 / 用户配置 都在 ./data 卷,跟容器寿命无关
#   - 重启容器不丢任何数据
#   - 即使新版本启动失败,旧数据完整保留,可以改 image tag 回滚

set -eu

# ============================================================
# 配置(改成你实际的)
# ============================================================
PROJ_DIR="/volume1/docker/media-manager"
DOCKER="/var/packages/Docker/target/usr/bin/docker"
DC="/var/packages/Docker/target/usr/bin/docker-compose"

# ============================================================
# 工具函数
# ============================================================
log() { echo "[$(date '+%H:%M:%S')] $*"; }
ok()  { echo "  ✓ $*"; }
err() { echo "  ✗ $*" >&2; }

# ============================================================
# 主流程
# ============================================================
cd "$PROJ_DIR" || { err "找不到目录 $PROJ_DIR"; exit 1; }

[ -f docker-compose.yml ] || { err "找不到 docker-compose.yml"; exit 1; }

# 检查需要 sudo
if [ "$(id -u)" -ne 0 ]; then
    log "需要 sudo 权限,会提示密码..."
    SUDO="sudo"
else
    SUDO=""
fi

log "==== 1/4 记录当前版本 (用于失败回滚) ===="
OLD_IMAGE_ID=$($SUDO $DOCKER inspect media-manager --format '{{.Image}}' 2>/dev/null || echo "none")
OLD_VERSION=$(curl -s --max-time 3 http://127.0.0.1:10001/api/health 2>/dev/null \
              | python3 -c 'import sys,json; print(json.load(sys.stdin).get("commit","unknown")[:7])' 2>/dev/null || echo "unknown")
ok "当前 image ID: ${OLD_IMAGE_ID:7:12}"
ok "当前版本 commit: $OLD_VERSION"

log "==== 2/4 拉取最新镜像 ===="
log "  这一步可能很慢 (国内拉 ghcr.io 通常 5-10 分钟)"
log "  如果超过 15 分钟没动,Ctrl+C 中断,改用方案 C(外部机器拉)"
log ""
$SUDO $DC pull
ok "镜像拉取完成"

log "==== 3/4 重新创建容器 ===="
$SUDO $DC up -d
ok "容器已重启"

log "==== 4/4 等待健康检查并清理旧镜像 ===="
echo -n "  健康检查 "
NEW_VERSION=""
for i in $(seq 1 30); do
    if curl -s --max-time 2 http://127.0.0.1:10001/api/health > /tmp/.mm-health.json 2>/dev/null; then
        NEW_VERSION=$(python3 -c 'import json; print(json.load(open("/tmp/.mm-health.json")).get("commit","")[:7])' 2>/dev/null || echo "")
        if [ -n "$NEW_VERSION" ]; then
            echo " ✓"
            ok "新版本上线: $NEW_VERSION"
            break
        fi
    fi
    echo -n "."
    sleep 2
done

if [ -z "$NEW_VERSION" ]; then
    echo ""
    err "健康检查 60 秒未通过!容器可能启动失败"
    err "看日志诊断: sudo $DC logs --tail 50"
    err "回滚命令: 改 docker-compose.yml 里 image: tag 加 sha-$OLD_VERSION 后 sudo $DC up -d"
    exit 2
fi

# 清理 dangling 镜像 (老版本,被新版本顶替的)
$SUDO $DOCKER image prune -f >/dev/null 2>&1 || true
ok "已清理 dangling 旧镜像"

log "==== 完成 ===="
echo ""
if [ "$OLD_VERSION" = "$NEW_VERSION" ]; then
    log "ℹ 已经是最新版,版本号没变 ($NEW_VERSION)"
else
    log "✓ 升级成功: $OLD_VERSION → $NEW_VERSION"
fi
echo ""
log "浏览器刷新一下页面 (Ctrl+Shift+R / Cmd+Shift+R) 看到新前端"

rm -f /tmp/.mm-health.json
