#!/usr/bin/env python3
"""
从 OCI/Docker registry 直接下载镜像 + 打包成 docker load 可读的 tar。
不依赖 docker / skopeo,只用 stdlib + requests。

用法:
    python3 pull-image.py ghcr.io/boylengit/media-manager:latest /tmp/mm.tar amd64

参考:
- Docker registry HTTP API V2: https://docs.docker.com/registry/spec/api/
- Docker image spec (load 格式): https://github.com/moby/moby/blob/master/image/spec/v1.2.md
"""
import gzip
import hashlib
import io
import json
import os
import sys
import tarfile
import urllib.request
import urllib.parse
from pathlib import Path

UA = "python-pull/1.0"


# 支持的 registry 配置
#   - auth_url 可选:为空表示该 mirror 直接匿名访问 v2,无需 token
#   - host: manifest/blob 主机
REGISTRIES = {
    "ghcr.io": {
        "host": "ghcr.io",
        "auth_url": "https://ghcr.io/token?service=ghcr.io&scope=repository:{repo}:pull",
    },
    "docker.io": {
        "host": "registry-1.docker.io",
        "auth_url": "https://auth.docker.io/token?service=registry.docker.io&scope=repository:{repo}:pull",
    },
    # 国内 docker hub 镜像加速 — 注意:多数已不再开放白嫖,以下是仍可用的
    # registry.cyou 直接匿名透传,适合 Mac 在国内电信网络下使用
    "registry.cyou": {
        "host": "registry.cyou",
        "auth_url": None,  # 无需 token
    },
    "docker.xuanyuan.me": {
        "host": "docker.xuanyuan.me",
        "auth_url": None,
    },
    "docker.1ms.run": {
        "host": "docker.1ms.run",
        "auth_url": "https://docker.1ms.run/openapi/v1/auth/token/docker.1ms.run/repository:{repo}:pull",
    },
    "docker.m.daocloud.io": {
        "host": "docker.m.daocloud.io",
        "auth_url": "https://docker.m.daocloud.io/auth.docker.io/token?service=registry.docker.io&scope=repository:{repo}:pull",
    },
}


def http_get(url, headers=None, follow=True):
    req = urllib.request.Request(url, headers={**(headers or {}), "User-Agent": UA})
    return urllib.request.urlopen(req, timeout=120)


def get_token(registry, repo):
    """匿名拿 token;若 mirror 不需要 token(auth_url=None)则返回 None。"""
    cfg = REGISTRIES[registry]
    if not cfg.get("auth_url"):
        return None
    url = cfg["auth_url"].format(repo=repo)
    with http_get(url) as r:
        data = json.load(r)
        # 不同 mirror 的字段:standard 'token',兼容 'access_token'
        return data.get("token") or data.get("access_token")


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"} if token else {}


def get_manifest(registry, repo, tag, token, accept):
    host = REGISTRIES[registry]["host"]
    url = f"https://{host}/v2/{repo}/manifests/{urllib.parse.quote(tag, safe='')}"
    headers = {**_auth_header(token), "Accept": accept}
    with http_get(url, headers) as r:
        return json.load(r), r.headers.get("Docker-Content-Digest")


def download_blob(registry, repo, digest, token, out_path):
    """下载 blob,带进度。"""
    host = REGISTRIES[registry]["host"]
    url = f"https://{host}/v2/{repo}/blobs/{digest}"
    headers = _auth_header(token)
    with http_get(url, headers) as r:
        total = int(r.headers.get("Content-Length", 0))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        h = hashlib.sha256()
        downloaded = 0
        last_print = 0
        with open(out_path, "wb") as f:
            while True:
                chunk = r.read(64 * 1024)
                if not chunk:
                    break
                h.update(chunk)
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0 and (downloaded - last_print) > 5 * 1024 * 1024:
                    last_print = downloaded
                    pct = downloaded * 100 / total
                    print(
                        f"      下载 {downloaded // 1024 // 1024} / {total // 1024 // 1024} MB ({pct:.0f}%)",
                        flush=True,
                    )
        actual = "sha256:" + h.hexdigest()
        if actual != digest:
            raise ValueError(f"digest 不匹配: 期望 {digest} 实际 {actual}")
    return downloaded


def main():
    if len(sys.argv) < 3:
        print("用法: pull-image.py <image:tag> <output.tar> [arch]")
        sys.exit(1)

    full = sys.argv[1]
    out_tar = Path(sys.argv[2]).resolve()
    arch = sys.argv[3] if len(sys.argv) > 3 else "amd64"

    # parse "ghcr.io/boylengit/media-manager:latest" 或 "linuxserver/prowlarr:latest"
    if ":" not in full.rsplit("/", 1)[-1]:
        full += ":latest"
    registry_path, tag = full.rsplit(":", 1)
    if "/" in registry_path:
        parts = registry_path.split("/", 1)
        # 第一段如果含点或冒号,认为是 registry host;否则是 docker hub 命名空间
        if "." in parts[0] or ":" in parts[0]:
            registry, repo = parts[0], parts[1]
        else:
            registry, repo = "docker.io", registry_path
    else:
        # 单段,例如 "alpine" -> docker.io/library/alpine
        registry, repo = "docker.io", f"library/{registry_path}"

    # docker hub 单段镜像(如 jellyfin/jellyfin)默认 library/ 前缀逻辑已上面处理
    # 没有命名空间的纯名 (如 "alpine") -> library/alpine
    if registry == "docker.io" and "/" not in repo:
        repo = f"library/{repo}"

    if registry not in REGISTRIES:
        print(f"不支持的 registry: {registry} (支持 ghcr.io, docker.io)")
        sys.exit(1)

    print(f"== 镜像: {registry}/{repo}:{tag} arch={arch}")

    print("1. 获取匿名 token...")
    token = get_token(registry, repo)
    print(f"   token: {'len=' + str(len(token)) if token else '(none, anonymous mirror)'}")

    print("2. 获取 manifest list...")
    list_manifest, _ = get_manifest(
        registry,
        repo,
        tag,
        token,
        accept=", ".join(
            [
                "application/vnd.docker.distribution.manifest.list.v2+json",
                "application/vnd.oci.image.index.v1+json",
                "application/vnd.docker.distribution.manifest.v2+json",
            ]
        ),
    )
    media_type = list_manifest.get("mediaType", "")
    print(f"   mediaType: {media_type}")

    # 如果是 list/index,选择对应架构的 manifest
    if "list" in media_type or "index" in media_type:
        target = None
        for m in list_manifest.get("manifests", []):
            p = m.get("platform", {})
            if p.get("architecture") == arch and p.get("os") == "linux":
                target = m
                break
        if not target:
            print(f"   找不到 linux/{arch}")
            sys.exit(1)
        print(f"   选中 manifest digest: {target['digest']}")
        manifest, _ = get_manifest(
            registry, repo, target["digest"], token, accept=target["mediaType"]
        )
    else:
        manifest = list_manifest

    config_digest = manifest["config"]["digest"]
    layers = manifest["layers"]
    print(f"3. 镜像有 {len(layers)} 层")

    # 临时工作目录
    work = out_tar.with_suffix(".workdir")
    work.mkdir(parents=True, exist_ok=True)

    # 下载 config (已存在则跳过)
    print(f"4. 下载 config blob {config_digest[:20]}...")
    config_path = work / f"{config_digest.split(':')[1]}.json"
    if config_path.exists() and config_path.stat().st_size > 0:
        print(f"   [cached] {config_path.stat().st_size} bytes")
    else:
        download_blob(registry, repo, config_digest, token, config_path)

    # 下载 layers
    print(f"5. 下载 {len(layers)} 个 layer (并发 3 个)...")
    import concurrent.futures

    layer_files = []  # 顺序保留,与 manifest 一致
    layer_to_path = {}

    def _dl(idx, layer):
        digest = layer["digest"]
        size = layer.get("size", 0)
        size_mb = size / 1024 / 1024
        path = work / f"{digest.split(':')[1]}.tar.gz"
        # 已下完的 (大小匹配) 跳过 — 实现断点续传
        if path.exists() and size > 0 and path.stat().st_size == size:
            print(f"   [{idx + 1}/{len(layers)}] {digest[:20]} ({size_mb:.1f} MB) [cached]")
            return idx, path
        if path.exists():
            path.unlink()  # 损坏的部分文件,重下
        print(f"   [{idx + 1}/{len(layers)}] {digest[:20]} ({size_mb:.1f} MB)")
        download_blob(registry, repo, digest, token, path)
        return idx, path

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        results = list(ex.map(lambda x: _dl(*x), enumerate(layers)))
    for idx, path in sorted(results):
        layer_files.append(path)

    # 生成 manifest.json (docker load 需要这个)
    config_filename = f"{config_digest.split(':')[1]}.json"
    layer_archives = []
    for layer_path in layer_files:
        # docker load 期望 layer 是 .tar (未压缩) 或者一个目录
        # 但 docker 24+ 也接受 .tar.gz,我们直接用 .tar.gz 文件路径
        layer_archives.append(f"{layer_path.name}")

    # 镜像 RepoTags:docker.io 镜像不带 registry 前缀(惯例 + load 后干净)
    if registry == "docker.io":
        repo_display = repo[len("library/"):] if repo.startswith("library/") else repo
        full_tag = f"{repo_display}:{tag}"
    else:
        full_tag = f"{registry}/{repo}:{tag}"

    manifest_json = [
        {
            "Config": config_filename,
            "RepoTags": [full_tag],
            "Layers": layer_archives,
        }
    ]
    (work / "manifest.json").write_text(json.dumps(manifest_json))

    # 生成 repositories 文件 (老版本 docker 也需要)
    repo_key = full_tag.rsplit(":", 1)[0]
    repositories = {repo_key: {tag: layers[-1]["digest"].split(":")[1]}}
    (work / "repositories").write_text(json.dumps(repositories))

    # 打包成 tar
    print(f"6. 打包成 {out_tar} ...")
    with tarfile.open(out_tar, "w") as tar:
        # 加 manifest.json (必须)
        tar.add(work / "manifest.json", arcname="manifest.json")
        tar.add(work / "repositories", arcname="repositories")
        tar.add(config_path, arcname=config_filename)
        for layer_path in layer_files:
            tar.add(layer_path, arcname=layer_path.name)

    size_mb = out_tar.stat().st_size / 1024 / 1024
    print(f"   完成: {out_tar} ({size_mb:.1f} MB)")

    # 清理临时文件
    import shutil

    shutil.rmtree(work)
    print("7. ✓ 全部完成")


if __name__ == "__main__":
    main()
