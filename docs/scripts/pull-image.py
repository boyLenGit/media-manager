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


def http_get(url, headers=None, follow=True):
    req = urllib.request.Request(url, headers={**(headers or {}), "User-Agent": UA})
    return urllib.request.urlopen(req, timeout=120)


def get_token(repo):
    """匿名拿 ghcr.io token。"""
    url = f"https://ghcr.io/token?service=ghcr.io&scope=repository:{repo}:pull"
    with http_get(url) as r:
        return json.load(r)["token"]


def get_manifest(repo, tag, token, accept):
    url = f"https://ghcr.io/v2/{repo}/manifests/{urllib.parse.quote(tag, safe='')}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": accept,
    }
    with http_get(url, headers) as r:
        return json.load(r), r.headers.get("Docker-Content-Digest")


def download_blob(repo, digest, token, out_path):
    """下载 blob,带进度。"""
    url = f"https://ghcr.io/v2/{repo}/blobs/{digest}"
    headers = {"Authorization": f"Bearer {token}"}
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

    # parse "ghcr.io/boylengit/media-manager:latest"
    if "/" not in full:
        print("镜像名格式不对,需要 registry/path:tag")
        sys.exit(1)
    if ":" not in full.rsplit("/", 1)[-1]:
        full += ":latest"
    registry_path, tag = full.rsplit(":", 1)
    parts = registry_path.split("/", 1)
    registry, repo = parts[0], parts[1]
    if registry != "ghcr.io":
        print(f"目前只支持 ghcr.io,你传的是 {registry}")
        sys.exit(1)

    print(f"== 镜像: {repo}:{tag} arch={arch}")

    print("1. 获取匿名 token...")
    token = get_token(repo)
    print(f"   token len: {len(token)}")

    print("2. 获取 manifest list...")
    list_manifest, _ = get_manifest(
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
        manifest, _ = get_manifest(repo, target["digest"], token, accept=target["mediaType"])
    else:
        manifest = list_manifest

    config_digest = manifest["config"]["digest"]
    layers = manifest["layers"]
    print(f"3. 镜像有 {len(layers)} 层")

    # 临时工作目录
    work = out_tar.with_suffix(".workdir")
    work.mkdir(parents=True, exist_ok=True)

    # 下载 config
    print(f"4. 下载 config blob {config_digest[:20]}...")
    config_path = work / f"{config_digest.split(':')[1]}.json"
    download_blob(repo, config_digest, token, config_path)

    # 下载 layers
    print(f"5. 下载 {len(layers)} 个 layer (并发 3 个)...")
    import concurrent.futures

    layer_files = []  # 顺序保留,与 manifest 一致
    layer_to_path = {}

    def _dl(idx, layer):
        digest = layer["digest"]
        size = layer.get("size", 0)
        size_mb = size / 1024 / 1024
        print(f"   [{idx + 1}/{len(layers)}] {digest[:20]} ({size_mb:.1f} MB)")
        path = work / f"{digest.split(':')[1]}.tar.gz"
        download_blob(repo, digest, token, path)
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

    manifest_json = [
        {
            "Config": config_filename,
            "RepoTags": [f"{registry}/{repo}:{tag}"],
            "Layers": layer_archives,
        }
    ]
    (work / "manifest.json").write_text(json.dumps(manifest_json))

    # 生成 repositories 文件 (老版本 docker 也需要)
    repositories = {f"{registry}/{repo}": {tag: layers[-1]["digest"].split(":")[1]}}
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
