"""探测当前进程能访问到的"挂载根目录"。

设计目的:
- Docker 容器场景下,用户在 Web UI 加扫描路径时容易填错(把宿主机路径当容器内路径)
- 这个服务通过解析 /proc/self/mountinfo 找出容器里所有 bind mount,
  让前端能展示给用户「你目前能扫描这些目录」

如果不在容器里跑(开发模式),返回若干常见的根目录作为候选(/Users, /Volumes, /, /home, /mnt 等)。
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


# 容器里这些路径属于"系统内置",过滤掉不展示
_INTERNAL_PATHS = {
    "/",
    "/proc",
    "/sys",
    "/dev",
    "/dev/pts",
    "/dev/mqueue",
    "/dev/shm",
    "/etc/hostname",
    "/etc/hosts",
    "/etc/resolv.conf",
    "/sys/fs/cgroup",
    "/run",
    "/tmp",
    "/var/lib/docker",
    "/app",  # 我们后端代码本身在的位置
    "/app/backend/data",  # 持久化数据,不是给用户扫的
    "/usr",
    "/lib",
    "/lib64",
    "/bin",
    "/sbin",
    "/var",
    "/root",
    "/home",
    "/opt",
    "/media",  # 不过滤这个,/media 通常就是用户挂的
}

# 这些是用户挂载的"明显信号":bind mount + 不在系统路径下
_INTERESTING_FS_TYPES = {"ext4", "btrfs", "xfs", "zfs", "nfs", "nfs4", "cifs", "fuse"}


@dataclass
class MountInfo:
    """容器内一个挂载点的精简信息。"""

    path: str  # 容器内路径,如 "/media"
    fs_type: str  # 文件系统类型,如 "btrfs"
    is_readonly: bool
    exists: bool  # 路径是否真存在(防御性)
    is_dir: bool


def in_container() -> bool:
    """简单判断是否在容器里跑。"""
    if Path("/.dockerenv").exists():
        return True
    try:
        with open("/proc/1/cgroup") as f:
            return "docker" in f.read() or "containerd" in f.read()
    except OSError:
        return False


def _parse_mountinfo() -> list[dict]:
    """解析 /proc/self/mountinfo,返回 [{mount_point, fs_type, options}]"""
    try:
        with open("/proc/self/mountinfo") as f:
            lines = f.read().splitlines()
    except OSError:
        return []

    out: list[dict] = []
    for line in lines:
        # /proc/self/mountinfo 格式参考 man 5 proc:
        # 36 35 98:0 /mnt1 /mnt parent_options - ext3 /dev/root rw,errors=continue
        # 我们关心:列5(mount point) + ' - ' 后的 fs_type
        parts = line.split(" - ", 1)
        if len(parts) != 2:
            continue
        left = parts[0].split()
        right = parts[1].split()
        if len(left) < 6 or len(right) < 1:
            continue
        mount_point = left[4]
        mount_options = left[5]
        fs_type = right[0]
        out.append(
            {
                "mount_point": mount_point,
                "fs_type": fs_type,
                "options": mount_options,
            }
        )
    return out


def list_user_mounts() -> list[MountInfo]:
    """返回用户在容器里能扫描的挂载点。

    策略:
    - 容器内:解析 /proc/self/mountinfo,找出 bind mount(从宿主机挂进来的)
    - 容器外(开发):返回若干常见的可写根目录作为候选
    """
    if not in_container():
        # 开发场景:列举一些常见目录
        candidates = ["/Users", "/Volumes", "/home", "/mnt", "/data"]
        out = []
        for p in candidates:
            pth = Path(p)
            if pth.exists() and pth.is_dir():
                out.append(
                    MountInfo(
                        path=p,
                        fs_type="local",
                        is_readonly=not os.access(p, os.W_OK),
                        exists=True,
                        is_dir=True,
                    )
                )
        return out

    # 容器内
    raw = _parse_mountinfo()
    seen: set[str] = set()
    out: list[MountInfo] = []

    for m in raw:
        mp = m["mount_point"]
        # 过滤系统挂载
        if mp in _INTERNAL_PATHS:
            continue
        # 过滤系统挂载子路径(/sys/* /proc/* /dev/* 都不是给用户的)
        if any(
            mp.startswith(prefix + "/")
            for prefix in ("/proc", "/sys", "/dev", "/run", "/tmp", "/usr", "/lib", "/sbin", "/bin")
        ):
            continue
        # 过滤已经处理过的(同一路径可能多次出现)
        if mp in seen:
            continue
        seen.add(mp)

        path = Path(mp)
        is_readonly = "ro" in m["options"].split(",")
        out.append(
            MountInfo(
                path=mp,
                fs_type=m["fs_type"],
                is_readonly=is_readonly,
                exists=path.exists(),
                is_dir=path.exists() and path.is_dir(),
            )
        )

    return out
