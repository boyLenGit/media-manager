# Jackett / Prowlarr 配置教程

> Media Manager 不内置任何资源搜索源。本教程帮你配置 **Jackett** 或 **Prowlarr** 作为索引器代理,然后把它接入 Media Manager 的搜索功能。
>
> **合规声明**:你需要确保自己有权访问、下载、保存和播放对应资源。Media Manager 团队不对用户的搜索源选择负责。

---

## 0. 它们是什么?为什么要装?

| 组件 | 作用 | 类比 |
|---|---|---|
| **Jackett** | 老牌的 BT/磁力**索引器代理**,把上百个 BT 站的搜索接口统一成一种叫 **Torznab** 的标准协议 | 老干部 |
| **Prowlarr** | Jackett 的现代替代品,UI 更好、维护更活跃、支持自动同步到 Sonarr/Radarr 等 | 后浪 |
| **Media Manager** | 通过 **Torznab 协议**调用上面两位中的任意一个,展示聚合搜索结果 + 一键下载到 qBittorrent | 老板 |

**两者都是给你自己的 BT 账号(公网/私有站)做"中转翻译"用的**,本身不存储资源。Media Manager 只需要它们其中一个。

> **建议**:新装的话直接选 **Prowlarr**(更现代),已有 Jackett 就继续用。

---

## 1. 部署 Jackett 或 Prowlarr

### 方式 A:Docker(推荐 — 群晖/UNRAID/Linux 通用)

在 Media Manager 项目目录(或你自己习惯的目录)新建 `indexer-compose.yml`:

```yaml
services:
  # 二选一:Jackett
  jackett:
    image: linuxserver/jackett:latest
    container_name: jackett
    environment:
      PUID: "1000"          # 群晖里改成你 NAS 用户的 UID,可在 SSH 里 id <username> 查
      PGID: "100"           # 群晖默认是 users 组 = 100
      TZ: "Asia/Shanghai"
    volumes:
      - ./jackett-config:/config
      - ./jackett-downloads:/downloads     # .torrent 文件落盘位置(可选)
    ports:
      - "9117:9117"
    restart: unless-stopped

  # 或 Prowlarr (更推荐)
  prowlarr:
    image: linuxserver/prowlarr:latest
    container_name: prowlarr
    environment:
      PUID: "1000"
      PGID: "100"
      TZ: "Asia/Shanghai"
    volumes:
      - ./prowlarr-config:/config
    ports:
      - "9696:9696"
    restart: unless-stopped
```

启动:

```bash
# 只启 Prowlarr
docker compose -f indexer-compose.yml up -d prowlarr

# 或只启 Jackett
docker compose -f indexer-compose.yml up -d jackett
```

### 方式 B:群晖 Container Manager

1. **套件中心 / Docker** → 安装 Container Manager
2. **注册表** → 搜索 `linuxserver/jackett` 或 `linuxserver/prowlarr` → **下载**
3. **映像** → 双击下载的镜像 → 创建容器
4. 配置:
   - **网络**:`bridge` 或 `host`,简单点用 `host`
   - **端口**:Jackett `9117`,Prowlarr `9696`
   - **存储空间**:挂载一个 NAS 目录到 `/config`(如 `/volume1/docker/prowlarr/config`)
   - **环境变量**:`PUID=1026 PGID=100 TZ=Asia/Shanghai`(`PUID` 用 `id <你的群晖用户>` 命令查)
5. 应用 → 启动

### 方式 C:Windows 直装(仅限本地折腾)

去 https://github.com/Jackett/Jackett/releases 或 https://prowlarr.com/ 下载 Windows 安装包,一键安装即可。

---

## 2. 首次访问 + 设置密码

启动成功后,浏览器打开:

- **Jackett**:`http://<你的-NAS-IP>:9117`
- **Prowlarr**:`http://<你的-NAS-IP>:9696`

**第一次进去会提示设置密码**(强烈推荐设,因为这服务能搜你账号下的资源)。

---

## 3. 找到 API Key

> 这是接入 Media Manager 必备的凭据。

### Jackett

打开 `http://nas:9117`,**右上角**就有一个 **API Key** 文本框,直接复制。

### Prowlarr

`http://nas:9696` → **左上角菜单** → **Settings** → **General** → **Security** 下有 **API Key**,旁边眼睛图标点开复制。

---

## 4. 添加索引器(就是 BT 站)

### Jackett

1. 主页点 **「Add indexer」** 按钮
2. 列表里搜你想用的站点,例如:
   - 公开站:`nyaa.si`、`1337x`、`tpb`、`yts`、`eztv`
   - 中文公开:`btsow`、`cili`、`btdig`(可用性看运气)
   - 私有站:`hdsky`、`mteam`、`pthome`、`nicept` 等(需要你自己有账号)
3. 公开站直接点 **「+」** 添加;私有站要填 cookie 或账号密码
4. 添加完后点该行的 **「Test」**,绿色 ✅ 就是配好了

### Prowlarr

1. 左侧菜单 **Indexers** → 右上 **「Add Indexer」**
2. 同样可以筛选、搜索、添加
3. **小贴士**:Prowlarr 还可以在 **Indexers → All** 一键添加多个公开索引器

> 如果某些站添加后老是 401/403,通常是该站要登录、需要 FlareSolverr(Cloudflare 防护反代)、或被 GFW 拦,Google 一下站名 + flaresolverr 即可。

---

## 5. 在 Media Manager 中配置

打开 Media Manager:`http://localhost:8000`(或你的 NAS 地址)

1. 登录后 → **设置 → 搜索源** → **添加搜索源**
2. 按下表填写:

### 选项 A:接入 Jackett

| 字段 | 值 | 说明 |
|---|---|---|
| 名称 | `Jackett` | 任意,自己看的 |
| 类型 | **Torznab (Jackett/Prowlarr)** | 我们后端唯一支持的协议 |
| API 地址 | `http://<nas-ip>:9117/api/v2.0/indexers/all/results/torznab/api` | 注意 `all` 表示**搜索所有已添加的 indexer**;也可以替换成具体某个 indexer ID |
| API Key | 第 3 步复制的那串 | |
| 默认分类 | 留空 / 或填具体分类(见下方) | 用来收窄搜索范围 |
| 启用 | ✅ ON | |

### 选项 B:接入 Prowlarr

| 字段 | 值 |
|---|---|
| 名称 | `Prowlarr` |
| 类型 | **Torznab (Jackett/Prowlarr)** |
| API 地址 | `http://<nas-ip>:9696/1/api?t=search` |
| API Key | Prowlarr 的 API Key |
| 默认分类 | 同上 |
| 启用 | ✅ ON |

> Prowlarr 的 URL 路径里那个 `1` 是 indexer 的 ID,代表第一个 indexer。如果你想搜所有,把 URL 改成
> `http://<nas-ip>:9696/api/v1/search` 这种 Prowlarr 标准接口形式 —— 但本系统当前的 Torznab 适配器只支持单 indexer 路径。**最简单的做法是给每个 indexer 在 Media Manager 里建一条搜索源**,Prowlarr 设置页里可以看到每个 indexer 对应的 ID 数字。

3. 保存 → 点该行的 **「测试」** 按钮 → 应该弹绿色 ✅ "连接正常"

---

## 6. 试一下搜索效果

回到 Media Manager → **搜索** 页 → 输入关键词(如 `Inception`)→ **搜索**

你会看到:

- 顶栏显示总命中数
- 表格列出每条结果的 **标题 / 来源 / 大小 / 种子数 / 发布时间 / 重复检测标记**
- **重复检测**:如果你库里已经有同名/同 hash 的资源,会显示 🟡 "高度疑似" 或 🔴 "已存在",防止重复下载
- 点 **「下载」** 按钮 → 自动调 qBittorrent 添加任务(qB 需要先在「设置 → 下载器」配好)

---

## 7. Torznab 分类码速查

填到「默认分类」字段里,逗号分隔可填多个:

| 分类码 | 含义 |
|---|---|
| `2000` | 全部电影 |
| `2030` | Movies/SD |
| `2040` | Movies/HD (1080p) |
| `2045` | Movies/UHD (4K) |
| `2050` | Movies/3D |
| `5000` | 全部剧集 |
| `5030` | TV/SD |
| `5040` | TV/HD |
| `5045` | TV/UHD |
| `5070` | TV/Anime |
| `5080` | TV/Documentary |
| `3000` | 全部音乐 |
| `7000` | 全部 Books |

**实践建议**:
- 看电影主用 → `2000,2040,2045`
- 看剧主用 → `5000,5040,5045`
- 看动漫主用 → `5070`
- **建议为不同场景在 Media Manager 里建多条搜索源**,例如「Jackett-电影」「Jackett-剧集」「Jackett-动漫」分别配不同 cat,搜索时心智更清爽

---

## 8. 常见问题

### Q1: 测试连接报错 `not_configured` 或超时

- 检查 Media Manager 容器**能否访问** Jackett/Prowlarr 容器
- 如果两边都是 docker compose 跑的,推荐放在**同一个 compose 网络**里,或者 NAS 用 `host` 网络模式
- URL 用 `http://nas-lan-ip:9117/...` 而不是 `http://localhost:...` (容器里 localhost 是容器自己)

### Q2: 索引器搜不到结果

- 在 Jackett/Prowlarr **自带的搜索界面**先搜一下确认它能正常工作
- 私有站的 cookie 可能过期了(经常发生),重新填 cookie
- 用 `nyaa` 等公开站时如果 GFW 拦了,需要给容器配代理

### Q3: 出现 Cloudflare 验证拦截

需要额外部署 [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr),然后在 Jackett/Prowlarr 的 **Indexers** 设置页填 FlareSolverr 地址。

```yaml
# 加到 indexer-compose.yml
flaresolverr:
  image: ghcr.io/flaresolverr/flaresolverr:latest
  container_name: flaresolverr
  environment:
    LOG_LEVEL: info
    TZ: Asia/Shanghai
  ports:
    - "8191:8191"
  restart: unless-stopped
```

然后在 Jackett 右上角 → **FlareSolverr API URL** 填 `http://flaresolverr:8191`(同 compose 网络)或 `http://nas-ip:8191`。

### Q4: Prowlarr 的 URL 格式总配不对

简化做法:在 Prowlarr 的 indexer 列表里点某个 indexer → **Show Test**(或 More Info),它会告诉你具体的 Torznab 接口 URL 是什么。

### Q5: 私有站怎么不被风控

- 限制搜索频率(Media Manager 不会刷,但你别频繁手动点)
- 大部分 PT 站只允许 IP 白名单/账号 cookie,确保 cookie 是从你常用浏览器拿到的最新值
- 部分站(如 mteam)有专门的 API token,优先用 API token 而不是 cookie

---

## 9. 推荐配置组合

我个人推荐的 NAS 媒体栈,全部用 docker-compose 一起跑:

```
Media Manager      :8000   ← 你正在用的这个
Prowlarr      :9696   ← 索引器代理
qBittorrent   :8080   ← 下载器
Jellyfin      :8096   ← 媒体服务器(可选,网页播不了大文件时用)
FlareSolverr  :8191   ← Cloudflare 反代(可选)
```

它们彼此通过容器内部网络互联,在 Media Manager 里把对应的 URL 填上即可。所有 Web UI 都通过你的 NAS 反代(nginx / Caddy)+ HTTPS 暴露到公网就完美了。

---

## 10. 下一步

配好之后,完整流程:

```
1. Media Manager 搜索 「某电影名」
2. 系统并发查询所有启用的搜索源 → 聚合结果
3. 你看到结果 + 每个结果的「重复检测」标记
4. 点「下载」→ Media Manager 把磁力发给 qBittorrent
5. qBittorrent 下载完 → Media Manager 自动入库
6. 资源库里直接看到新资源,可网页播放或跳 Jellyfin
```

整个链路完全自动化。出问题先看后端日志:`docker compose logs -f media-manager` 或本地开发模式的 `/tmp/media-manager-backend.log`。

祝你折腾愉快!
