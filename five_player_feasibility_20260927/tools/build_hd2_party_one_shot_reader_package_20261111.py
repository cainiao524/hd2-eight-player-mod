"""Build the user-facing one-shot, read-only Party runtime reader package."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import uuid
import zipfile


BUILD = 25480438
ARCHIVE = "9ba626afa44a3aa3.patch_0"
EXPECTED_PATCH_SHA256 = "70d935078158cd8aa3f2b573a0cb934e6ce14fedd49dd46c4f80a67114cf2fb9"
GUID = "c2d2b2f6-6a08-4f63-9f65-6dcbbe7c3b11"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(patch_path: Path, output: Path) -> dict:
    patch = patch_path.read_bytes()
    patch_hash = sha256(patch)
    if patch_hash != EXPECTED_PATCH_SHA256:
        raise ValueError(f"unexpected one-shot patch hash: {patch_hash}")
    manifest = {
        "Version": 1,
        "Guid": str(uuid.UUID(GUID)),
        "Name": "HD2 Party One-Shot Reader",
        "Description": (
            "One-shot read-only Party/Session runtime reader with bundled HD2Scanner for Steam build 25480438. "
            "It reads bounded module, IAT, indirect-slot and PartyWin export data once. "
            "It never calls a game or Party function, writes memory, or installs hooks."
        ),
        "Dependencies": [{"Name": "Bingus Shared Loader", "MinimumVersion": "18"}],
        "Options": [{"Name": "Party one-shot reader", "Description": "Read-only diagnostic", "Include": ["Addon"]}],
    }
    provenance = {
        "schema": "hd2_party_one_shot_reader_package_v1",
        "package_id": "hd2-party-one-shot-reader",
        "revision": "2026-11-11-r13",
        "steam_build": BUILD,
        "archive": ARCHIVE,
        "inner_patch_sha256": patch_hash,
        "log_path": "%LOCALAPPDATA%/CowboyBingus/Helldivers2/Logs/HD2PartyApiProbe.log",
        "run_mode": "one_shot_after_frame_120",
        "read_only": True,
        "native_calls": False,
        "memory_writes": False,
        "hooks_installed": False,
        "multiplayer_verification": False,
    }
    instructions = """HD2 Party 一次性读取器（只读）

1. 关闭游戏。
2. 用 Mod 管理器导入这个 ZIP；如果手动安装，把 Addon/9ba626afa44a3aa3.patch_0
   放入游戏 data 目录，并使用一个已有的 mod patch 编号。请先备份原文件。
3. 从 Steam 正常启动 Helldivers 2，进入主菜单或舰船后等待约 20 秒，再退出游戏。
4. 把下面两个日志发回：
   %LOCALAPPDATA%\\CowboyBingus\\Helldivers2\\Logs\\HD2PartyApiProbe.log
   %LOCALAPPDATA%\\CowboyBingus\\Helldivers2\\Logs\\BingusSharedLoader.log
5. 读取器只执行一次；看到 DONE 后即可退出并恢复你备份的 patch 文件。

本包不改变人数、不创建房间、不加入房间，也不调用 Party API。它只为确认真实
运行时的 Session/Party 指针和调用槽位，不能作为 8 人 Mod 直接使用。
"""
    files = {
        "manifest.json": (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        "Addon/" + ARCHIVE: patch,
        "Addon/" + ARCHIVE + ".stream": b"",
        "Addon/" + ARCHIVE + ".gpu_resources": b"",
        "HD2-Party-OneShot-Reader-manifest.json": (json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        "README.zh-CN.txt": instructions.encode("utf-8"),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    pending = output.with_suffix(output.suffix + ".pending")
    with zipfile.ZipFile(pending, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for name, content in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            package.writestr(info, content)
    pending.replace(output)
    provenance["package_sha256"] = sha256(output.read_bytes())
    return provenance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--patch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build(args.patch, args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
