# Media Manager 文档目录

---

## 📚 给新接手的开发者(必读)

- **[tutorials/handover_cn.md](./tutorials/handover_cn.md)** — 项目交接文档,30 分钟读完能上手
- **[tutorials/api-cheatsheet_cn.md](./tutorials/api-cheatsheet_cn.md)** — 所有 API 接口速查

## 🚀 部署相关

- **[tutorials/synology-deploy_cn.md](./tutorials/synology-deploy_cn.md)** — 群晖 NAS 部署(DSM 7.2+ Container Manager)+ Watchtower 自动更新
- **[tutorials/synology-dsm71-deploy_cn.md](./tutorials/synology-dsm71-deploy_cn.md)** — **群晖 DSM 7.1 老 Docker 套件实战部署**(含 ghcr.io 拉取卡住、SSH SCP 协议、OCI manifest 兼容等坑的解决方案)
- **[tutorials/synology-dsm71-update_cn.md](./tutorials/synology-dsm71-update_cn.md)** — **群晖 DSM 7.1 老 Docker 更新教程**(3 种更新方案 + 一键脚本 + 回滚 + FAQ)
- **[tutorials/jackett-prowlarr_cn.md](./tutorials/jackett-prowlarr_cn.md)** — 配置 Jackett / Prowlarr 作为搜索源
- **[tutorials/custom-parser-request_cn.md](./tutorials/custom-parser-request_cn.md)** — 内置解析器清洗不干净某批文件名时,提交"新增文件名解析器"需求的填写模板

## 🔧 工具脚本

- **[scripts/pull-image.py](./scripts/pull-image.py)** — 纯 Python 实现的镜像拉取工具,绕开旧版 docker 拉 ghcr.io 多架构镜像的兼容问题
- **[scripts/update-on-synology.sh](./scripts/update-on-synology.sh)** — 群晖 DSM 7.1 一键更新脚本,自动 pull + recreate + 健康检查 + 清理

---

## 文档约定

- 文件名 `_cn.md` 后缀表示中文版,以后做英文版会用 `_en.md`
- 文档过时了或有遗漏,**直接更新**(handover_cn.md 第 14 节也是这样说的)
- 操作步骤推荐用代码块包起来,方便复制粘贴
- 涉及部署的文档**绝对不要包含真实 IP / 用户名 / 密码 / 域名**,用 `192.168.x.xxx`、`bo`、`xxx` 等占位符
