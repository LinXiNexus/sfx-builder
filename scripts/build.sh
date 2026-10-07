#!/usr/bin/env bash
# 用法：bash scripts/build.sh
# 可覆盖的环境变量：OUT_NAME / ENTRY / STUB_ARCH / MARKER / PAYLOAD_DIR
set -euo pipefail

OUT_NAME="${OUT_NAME:-Tool.exe}"
ENTRY="${ENTRY:-windows/app.exe}"
STUB_ARCH="${STUB_ARCH:-amd64}"
MARKER="${MARKER:-===SFX-PAYLOAD-2F7C9A31===}"
PAYLOAD_DIR="${PAYLOAD_DIR:-payloads}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v go  >/dev/null || { echo "缺少 go，请先安装 Go 1.22+"; exit 1; }
command -v zip >/dev/null || { echo "缺少 zip（apt install zip / brew install zip / pkg install zip）"; exit 1; }

echo "==> 1/3 编译 Windows 引导程序 (GOOS=windows GOARCH=${STUB_ARCH})"
mkdir -p build
GOOS=windows GOARCH="$STUB_ARCH" CGO_ENABLED=0 go build \
  -trimpath \
  -ldflags "-H windowsgui -s -w -X main.markerStr=${MARKER} -X main.entryPath=${ENTRY}" \
  -o build/stub.exe ./stub
# 提示：若 ldflags 注入不生效，把 main.xxx 改成完整导入路径（如 sfx/stub.markerStr）。

echo "==> 2/3 打包负载 (${PAYLOAD_DIR} -> build/payload.zip)"
if [ -f 使用说明.txt ]; then
  cp -f 使用说明.txt "${PAYLOAD_DIR}/使用说明.txt"
fi
rm -f build/payload.zip
( cd "$PAYLOAD_DIR" && zip -r -X -9 ../build/payload.zip . -x '.*' -x 'README.md' )

echo "==> 3/3 拼接单文件 ${OUT_NAME}"
cat build/stub.exe > "$OUT_NAME"
printf '%s' "$MARKER" >> "$OUT_NAME"
cat build/payload.zip >> "$OUT_NAME"

echo
echo "完成：${OUT_NAME}"
ls -lh "$OUT_NAME"
