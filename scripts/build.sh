#!/usr/bin/env bash
# 用法：bash scripts/build.sh
# 可覆盖的环境变量：OUT_NAME / ENTRY / STUB_ARCH / MARKER / PAYLOAD_DIR
set -euo pipefail

OUT_NAME="${OUT_NAME:-Tool.exe}"
ENTRY="${ENTRY:-windows/app.exe}"
# 默认 386：一个二进制同时兼容 32 位 / 64 位 Windows，ARM64 也能模拟运行
STUB_ARCH="${STUB_ARCH:-386}"
MARKER="${MARKER:-===SFX-PAYLOAD-2F7C9A31===}"
PAYLOAD_DIR="${PAYLOAD_DIR:-payloads}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v go  >/dev/null || { echo "✗ 缺少 go，请先安装 Go 1.20+"; exit 1; }
command -v zip >/dev/null || { echo "✗ 缺少 zip（apt install zip / brew install zip / pkg install zip）"; exit 1; }

filesize() {
  if stat -c %s "$1" >/dev/null 2>&1; then stat -c %s "$1"; else stat -f %z "$1"; fi
}

echo "==> 1/3 编译 Windows 引导程序 (GOOS=windows GOARCH=${STUB_ARCH})"
mkdir -p build
GOOS=windows GOARCH="$STUB_ARCH" CGO_ENABLED=0 go build \
  -trimpath \
  -ldflags "-H windowsgui -s -w -X main.markerStr=${MARKER} -X main.entryPath=${ENTRY}" \
  -o build/stub.exe ./stub
# 提示：若 ldflags 注入不生效，把 main.xxx 改成完整导入路径（如 sfx/stub.markerStr）。

echo "==> 2/3 打包负载 (${PAYLOAD_DIR} -> build/payload.zip)"
if [ ! -d "$PAYLOAD_DIR" ]; then
  echo "✗ 找不到负载目录：${PAYLOAD_DIR}"; exit 1
fi

# 检查负载是否为空（.gitkeep / README.md / 说明文档 都不算）
COUNT=$(cd "$PAYLOAD_DIR" && find . -type f \
        -not -name '.gitkeep' -not -name 'README.md' -not -name '使用说明.txt' | wc -l | tr -d ' ')
if [ "$COUNT" -eq 0 ]; then
  echo "✗ ${PAYLOAD_DIR}/ 里没有任何产物文件。"
  echo "  请先放入各平台产物，例如："
  echo "    ${PAYLOAD_DIR}/windows/app.exe"
  echo "    ${PAYLOAD_DIR}/android/app.apk"
  echo "    ${PAYLOAD_DIR}/ios/App.ipa"
  exit 1
fi
echo "    负载文件数：${COUNT}"

# 说明文档：打包时转成 UTF-8 BOM + CRLF，老版本 Windows 记事本也能正常显示中文
if [ -f 使用说明.txt ]; then
  printf '\xef\xbb\xbf' > "${PAYLOAD_DIR}/使用说明.txt"
  sed 's/$/\r/' 使用说明.txt >> "${PAYLOAD_DIR}/使用说明.txt"
fi

rm -f build/payload.zip
( cd "$PAYLOAD_DIR" && zip -r -X -9 ../build/payload.zip . \
    -x '.*' -x '*/.*' -x 'README.md' -x '*/README.md' )

if command -v unzip >/dev/null 2>&1; then
  echo "    负载内容："
  unzip -l build/payload.zip | sed -n '4,25p'
fi

echo "==> 3/3 拼接单文件 ${OUT_NAME}"
cat build/stub.exe > "$OUT_NAME"
printf '%s' "$MARKER" >> "$OUT_NAME"
cat build/payload.zip >> "$OUT_NAME"

SIZE=$(filesize "$OUT_NAME")
echo
echo "完成：${OUT_NAME}  (${SIZE} 字节)"
if [ "$SIZE" -gt 4294967296 ]; then
  echo "⚠️  超过 4 GiB，已启用 ZIP64，个别老旧解压工具可能不支持"
fi
ls -lh "$OUT_NAME"
