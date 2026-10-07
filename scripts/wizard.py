#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交互式打包向导：把各平台产物"拖"进来，然后自动打包。

用法：
    python3 scripts/wizard.py [--skip-build] [--skip-git]

流程：
    1. 逐个提示每个平台要放什么文件
    2. 你把文件拖进终端 / 粘贴路径 / 输入候选编号
    3. 校验文件是不是真的对应格式（看内容，不只看后缀）
    4. 确认后自动调用 scripts/build.sh 打包 + scripts/verify.py 校验
    5. 可选：自动 git 提交 / 推送 / 打 tag
"""
from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAYLOAD_DIR = ROOT / "payloads"


# ── 输出样式 ────────────────────────────────────────────────────────────
def _color() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


C = _color()


def c(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m" if C else s


def bold(s):  return c("1", s)
def dim(s):   return c("2", s)
def green(s): return c("32", s)
def yellow(s):return c("33", s)
def red(s):   return c("31", s)
def cyan(s):  return c("36", s)


def human(n: float) -> str:
    n = float(n)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{int(n)} B" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"


def shorten(s: str, n: int = 66) -> str:
    return s if len(s) <= n else "…" + s[-(n - 1):]


# ── 平台定义 ────────────────────────────────────────────────────────────
PLATFORMS = [
    {
        "key": "windows",
        "title": "Windows",
        "target": "windows/app.exe",
        "exts": [".exe"],
        "hint": "Windows 主程序 —— 整包的\"发动机\"，双击后运行的就是它",
        "required": True,
    },
    {
        "key": "android",
        "title": "安卓",
        "target": "android/app.apk",
        "exts": [".apk"],
        "hint": "安卓安装包（用户改后缀为 .zip 解压后安装）",
        "required": False,
    },
    {
        "key": "ios",
        "title": "iOS",
        "target": "ios/App.ipa",
        "exts": [".ipa"],
        "hint": "iOS 安装包（需已按渠道签名；用户解压后走 AltStore/TestFlight 安装）",
        "required": False,
    },
    {
        "key": "mac",
        "title": "macOS",
        "target": "mac/App.dmg",
        "exts": [".dmg", ".zip", ".pkg"],
        "hint": "macOS 安装包（dmg / pkg / 打包成 zip 的 .app）",
        "required": False,
    },
    {
        "key": "linux",
        "title": "Linux",
        "target": "linux/App.AppImage",
        "exts": [".appimage", ".run", ".deb", ".zip"],
        "hint": "Linux 安装包（AppImage / run / deb）",
        "required": False,
    },
]

SCAN_DIRS = [
    Path.home() / "storage" / "downloads",
    Path.home() / "storage" / "shared",
    Path.home() / "Downloads",
    Path("/sdcard/Download"),
    Path.home() / "Desktop",
    Path.cwd(),
    ROOT / "dist",
]


# ── 文件校验 ────────────────────────────────────────────────────────────
def read_head(p: Path, n: int) -> bytes:
    with open(p, "rb") as f:
        return f.read(n)


def read_tail(p: Path, n: int) -> bytes:
    size = p.stat().st_size
    with open(p, "rb") as f:
        if size > n:
            f.seek(-n, os.SEEK_END)
        return f.read()


def deep_check(p: Path, key: str) -> tuple[bool, str]:
    """看内容判断格式是否对得上，返回 (是否通过, 说明)。"""
    try:
        if key == "windows":
            head = read_head(p, 1 << 16)
            if head[:2] != b"MZ":
                return False, "不是 PE 文件（开头应为 MZ）"
            e = struct.unpack_from("<I", head, 0x3C)[0]
            if head[e:e + 4] != b"PE\x00\x00":
                return False, "有 MZ 头但找不到 PE 签名"
            machine = struct.unpack_from("<H", head, e + 4)[0]
            subsys = struct.unpack_from("<H", head, e + 24 + 68)[0]
            arch = {0x14C: "32 位", 0x8664: "64 位", 0xAA64: "ARM64"}.get(machine, f"0x{machine:04x}")
            sub = {2: "GUI 程序", 3: "控制台程序"}.get(subsys, f"subsystem={subsys}")
            return True, f"PE 可执行文件 · {arch} · {sub}"

        if key in ("android", "ios", "mac", "linux"):
            if read_head(p, 2) == b"PK":
                with zipfile.ZipFile(p) as z:
                    names = z.namelist()
                if key == "android":
                    has_manifest = "AndroidManifest.xml" in names
                    has_dex = any(n.startswith("classes") and n.endswith(".dex") for n in names)
                    if not (has_manifest or has_dex):
                        return False, "ZIP 里没有 AndroidManifest.xml / classes.dex，不像 APK"
                    return True, f"APK · {len(names)} 个条目"
                if key == "ios":
                    if not any(n.startswith("Payload/") for n in names):
                        return False, "ZIP 里没有 Payload/ 目录，不像 IPA"
                    return True, f"IPA · {len(names)} 个条目"
                if key == "mac":
                    if any(".app/" in n for n in names):
                        return True, f"macOS 应用包 · {len(names)} 个条目"
                    return True, f"ZIP 压缩包 · {len(names)} 个条目"
                return True, f"ZIP 压缩包 · {len(names)} 个条目"

            if key == "mac" and b"koly" in read_tail(p, 512):
                return True, "DMG 磁盘映像"
            if key == "linux":
                if read_head(p, 4) == b"\x7fELF":
                    return True, "ELF 可执行文件 / AppImage"
                head = read_head(p, 0x8006)
                if len(head) > 0x8001 and head[0x8001:0x8006] == b"CD001":
                    return True, "ISO 格式 AppImage"
            return True, "无法深度识别（按后缀放行）"
    except Exception as exc:  # noqa: BLE001
        return False, f"读取失败：{exc}"
    return True, "未校验"


# ── 候选文件扫描 ────────────────────────────────────────────────────────
def scan(exts: list[str], limit: int = 10) -> list[Path]:
    dirs: list[Path] = []
    for d in SCAN_DIRS:
        try:
            d = d.expanduser().resolve()
        except Exception:  # noqa: BLE001
            continue
        if d.is_dir() and d not in dirs:
            dirs.append(d)

    hits: list[Path] = []
    for d in dirs:
        base = len(d.parts)
        for root, subdirs, files in os.walk(d):
            if len(Path(root).parts) - base >= 3:
                subdirs[:] = []
            subdirs[:] = [s for s in subdirs if not s.startswith(".") and s not in ("Android", "obb", "data")]
            for f in files:
                if any(f.lower().endswith(e) for e in exts):
                    hits.append(Path(root) / f)
            if len(hits) > 80:
                break
        if len(hits) > 80:
            break

    seen, uniq = set(), []
    for h in hits:
        try:
            key = str(h.resolve())
        except Exception:  # noqa: BLE001
            key = str(h)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(h)

    uniq.sort(key=lambda x: x.stat().st_mtime if x.exists() else 0, reverse=True)
    return uniq[:limit]


def clean_path(raw: str) -> str:
    s = raw.strip()
    if s.startswith("file://"):
        s = s[7:]
    for q in ('"', "'"):
        if len(s) >= 2 and s.startswith(q) and s.endswith(q):
            s = s[1:-1]
    if os.name != "nt":
        s = s.replace("\\ ", " ")          # 拖拽时常见：空格被转义成 "\ "
    s = s.strip().strip('"').strip("'")
    return os.path.expanduser(s)


# ── 交互 ────────────────────────────────────────────────────────────────
def ask(prompt: str) -> str:
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def pick(plat: dict) -> Path | None:
    print()
    print(bold(f"── {plat['title']} ──") + "  " + dim(plat["target"]))
    print("   " + plat["hint"])
    print("   " + dim("（必需）" if plat["required"] else "（可选，直接回车跳过）"))

    cands = scan(plat["exts"])
    if cands:
        print(dim("   在本机找到这些候选："))
        for i, f in enumerate(cands, 1):
            size = human(f.stat().st_size) if f.exists() else "?"
            print(dim(f"     [{i}] {shorten(str(f), 58)}  {size}"))

    while True:
        raw = ask(cyan("   拖入文件 / 粘贴路径 / 输入编号 / 回车跳过 > ")).strip()

        if raw == "":
            if plat["required"]:
                print(yellow("   ⚠ 这是必需项。没有它，包里双击后没有程序可运行。"))
                if ask(cyan("   仍要跳过？(y/N) > ")).strip().lower() == "y":
                    return None
                continue
            return None

        if raw.isdigit() and cands and 1 <= int(raw) <= len(cands):
            path = cands[int(raw) - 1]
        else:
            path = Path(clean_path(raw))
            if not path.exists():
                parts = clean_path(raw).split()
                alt = next((Path(x) for x in parts if Path(x).exists()), None)
                if alt:
                    path = alt

        if not path.exists():
            print(red(f"   ✗ 找不到：{path}"))
            continue
        if not path.is_file():
            print(red(f"   ✗ 不是文件：{path}"))
            continue
        if path.stat().st_size == 0:
            print(red("   ✗ 空文件"))
            continue

        ok, note = deep_check(path, plat["key"])
        size = human(path.stat().st_size)
        if ok:
            print(green(f"   ✓ {note}  ·  {size}"))
            return path
        print(red(f"   ✗ 校验不通过：{note}"))
        print(dim(f"     文件：{path}（{size}）"))
        if ask(cyan("   仍要使用这个文件？(y/N) > ")).strip().lower() == "y":
            return path


def copy_in(plat: dict, src: Path) -> Path:
    dst_dir = PAYLOAD_DIR / plat["key"]
    dst_dir.mkdir(parents=True, exist_ok=True)
    for old in dst_dir.iterdir():          # 清掉同平台旧产物
        if old.is_file() and old.name != ".gitkeep":
            old.unlink()
    dst = PAYLOAD_DIR / plat["target"]
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    assert dst.is_file() and dst.stat().st_size > 0, f"复制失败：{dst}"
    return dst


def run(cmd: list[str]) -> int:
    print(dim("   $ " + " ".join(cmd)))
    return subprocess.call(cmd, cwd=ROOT)


# ── 主流程 ──────────────────────────────────────────────────────────────
def main() -> int:
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:  # noqa: BLE001
        pass
    args = set(sys.argv[1:])
    skip_build = "--skip-build" in args
    skip_git = "--skip-git" in args

    print()
    print(bold("╭──────────────────────────────────────────────╮"))
    print(bold("│   单文件多平台打包向导  ·  SFX Builder       │"))
    print(bold("╰──────────────────────────────────────────────╯"))
    print()
    print(" 我会把每个平台需要的东西逐个问清楚，你把文件")
    print(" 拖进终端就行（也可以粘贴路径，或直接输入编号）。")
    print(dim(" 全部确认后自动打包；随时 Ctrl+C 退出。"))

    chosen: dict[str, Path] = {}
    for plat in PLATFORMS:
        src = pick(plat)
        if src:
            chosen[plat["key"]] = src

    if not chosen:
        print()
        print(yellow("没有选择任何产物，已退出（什么都没改）。"))
        return 1

    # ── 汇总确认 ──
    print()
    print(bold("将要打包："))
    for plat in PLATFORMS:
        src = chosen.get(plat["key"])
        if src:
            ok, note = deep_check(src, plat["key"])
            print(f"  {green('✓')} {plat['title']:<8} ← {shorten(str(src), 52)}  {dim(note)}")
        else:
            print(f"  {dim('-')} {dim(plat['title'] + '（跳过）')}")

    if ask(cyan("\n开始打包？(Y/n) > ")).strip().lower() == "n":
        print("已取消，什么都没改。")
        return 1

    print()
    for plat in PLATFORMS:
        src = chosen.get(plat["key"])
        if src:
            dst = copy_in(plat, src)
            print(f"  放入 {dst.relative_to(ROOT)}")

    if skip_build:
        print(dim("\n（--skip-build：跳过打包）"))
        return 0

    print()
    print(bold("▶ 开始打包"))
    out_name = os.environ.get("OUT_NAME", "Tool.exe")
    if run(["bash", "scripts/build.sh"]) != 0:
        print(red("\n✗ 打包失败，请看上面的输出。"))
        return 1

    print()
    print(bold("▶ 校验产物"))
    run([sys.executable, "scripts/verify.py", out_name])

    if not skip_git:
        print()
        if ask(cyan("要提交并推送到 GitHub 吗？(y/N) > ")).strip().lower() == "y":
            msg = ask(cyan("提交说明（回车用默认）> ")).strip() or "chore: 更新各平台产物"
            run(["git", "add", "-A"])
            run(["git", "commit", "-m", msg])
            run(["git", "push"])
            if ask(cyan("打 tag 并发 Release？输入 tag 名（如 v1.0.0），回车跳过 > ")).strip():
                tag = ask(cyan("再确认一次 tag 名 > ")).strip()
                if tag:
                    run(["git", "tag", tag])
                    run(["git", "push", "origin", tag])

    print()
    print(green(bold("完成 ✔")) + f"  产物：{ROOT / out_name}")
    print(dim("   发布前建议先在真机上双击试一次。"))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断。")
        sys.exit(130)
