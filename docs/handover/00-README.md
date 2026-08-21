# Media Manager 交接文档

> 本目录是 Media Manager 项目的**结构化交接文档集**,供接手的开发者 / AI agent 快速理解项目全貌并上手。
>
> **最后更新**:2026-06-20(对应 commit `eddac4e` 之后)
> **仓库**:https://github.com/boyLenGit/media-manager
> **镜像**:`ghcr.io/boylengit/media-manager:latest`(Public)

---

## 这是什么项目(30 秒版)

**部署在群晖 NAS 上的轻量级私人媒体管理系统**。核心链路:

```
扫描本地视频文件 → 文件名智能解析 → 入库(标签/作者/类型)
   → 网页播放 / 外部播放器 / Jellyfin
   → 顺带管理 qBittorrent 下载、Torznab 搜索源、视频书签
```

定位是媒体资源的**"主入口 / 管理台"**,Jellyfin 只是它的一个可选播放目标,不是竞争关系。

---

## 阅读顺序

按顺序读,大约 40 分钟能建立完整认知:

| # | 文档 | 讲什么 | 谁该读 |
|---|---|---|---|
| **01** | [背景与目标](./01-背景与目标.md) | 为什么造这个轮子、解决什么痛点、和 Jellyfin/Plex 的区别、**非目标** | 所有人,先读 |
| **02** | [架构总览](./02-架构总览.md) | 技术栈、目录结构、请求数据流、四大 provider 扩展点 | 开发者 |
| **03** | [数据模型](./03-数据模型.md) | 22 张表、表间关系、migration 机制(无 Alembic) | 开发者 |
| **04** | [功能清单](./04-功能清单.md) | 已实现的每个功能 + UI 入口 + 后端接口 | 所有人 |
| **05** | [部署运维](./05-部署运维.md) | DSM 7.1 实战部署、镜像拉取(方案 C)、更新、当前 NAS 具体环境参数 | 运维 / 部署者 |
| **06** | [开发指南](./06-开发指南.md) | 本地起服务、改 schema、加解析器/搜索源、代码规范、不要做的事 | 开发者 |
| **07** | [已知问题与路线图](./07-已知问题与路线图.md) | backlog(按优先级)、踩过的坑 | 规划 / 开发者 |
| **08** | [运维知识库](./08-运维知识库.md) | qB/BitComet 差异、Prowlarr 接入、镜像源、BT 网络排障等实战 FAQ | 运维 / 用户 |

---

## 另有独立教程(docs/tutorials/)

这套交接文档是**总览 + 原理**,具体操作步骤见 `docs/tutorials/`:

| 文件 | 用途 |
|---|---|
| `synology-dsm71-deploy_cn.md` | DSM 7.1 老 Docker 套件从零部署(含 6 个坑) |
| `synology-dsm71-update_cn.md` | DSM 7.1 更新教程(3 种方案 + FAQ) |
| `jackett-prowlarr_cn.md` | 搜索源(Jackett/Prowlarr)配置 |
| `api-cheatsheet_cn.md` | REST API 速查 |
| `handover_cn.md` | **旧版**交接文档(单文件,较早期,本目录是它的升级替代) |

工具脚本见 `docs/scripts/`:
- `pull-image.py` — 纯 Python 从 registry 拉镜像打 tar(支持 ghcr.io / docker.io / 国内镜像 + 断点续传)
- `update-on-synology.sh` — NAS 一键更新脚本

---

## 一句话给下一个接手的人

> 这是一个**功能完成度已经很高**的私人 NAS 媒体管理器。核心扫描/播放/下载/搜索/书签/去重都跑通了并部署在生产(用户的群晖)。你接手后大概率是**做增量功能**(海报刮削、i18n、更多下载器)或**修实战 bug**,而不是大重构。先读 01 和 07,再挑一个 backlog 动手。
