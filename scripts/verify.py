#!/usr/bin/env python3
"""产物自检：PE 头 / 内嵌 zip 可读 / 关键条目是否存在。

用法：python3 scripts/verify.py Tool.exe [--full]
--full 会额外做全量 CRC 校验（大文件较慢）。
"""
import hashlib
import os
import sys
import zipfile
from pathlib import Path

EXPECT_WARN = ["windows/app.exe", "android/app.apk"]


def norm(name: str) -> str:
    return name[2:] if name.startswith("./") else name


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = Path(args[0] if args else os.environ.get("OUT_NAME", "Tool.exe"))
    if not path.is_file():
        print(f"x 找不到产物：{path}")
        return 1

    data = path.read_bytes()
    if data[:2] != b"MZ":
        print("x 缺少 PE(MZ) 文件头，Windows 无法运行")
        return 1
    print(f"OK PE 头正常，大小 {len(data) / 1048576:.1f} MiB")
    print(f"   SHA256 = {hashlib.sha256(data).hexdigest()}")

    if b"PK\x03\x04" not in data:
        print("x 没有找到内嵌的 ZIP 负载")
        return 1

    with zipfile.ZipFile(path) as z:
        names = sorted(z.namelist())
        print(f"OK 内嵌压缩包可读，共 {len(names)} 个条目：")
        for n in names[:50]:
            print("   -", n)
        if len(names) > 50:
            print(f"   ... 其余 {len(names) - 50} 个省略")
        if "--full" in sys.argv:
            bad = z.testzip()
            if bad:
                print(f"x CRC 校验失败：{bad}")
                return 1
            print("OK CRC 校验通过")

    have = {norm(n) for n in names}
    for r in EXPECT_WARN:
        if r not in have:
            print(f"WARN 建议条目缺失：{r}（该平台暂未支持可忽略）")

    print("OK 校验通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
