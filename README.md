# 单文件多平台分发工具（SFX Builder）

把一个 Windows 可执行引导程序 + 各平台产物（exe / apk / ipa / …）打成一个文件：

- **Windows 用户**：双击即用
- **安卓 / macOS / Linux 用户**：改后缀为 `.zip` 解压，取自己平台的包
- **iOS 用户**：解压取出 `.ipa`，走签名渠道安装

## 快速开始

```bash
# 1. 放入各平台产物
payloads/windows/app.exe
payloads/android/app.apk
payloads/ios/App.ipa

# 2. 本地构建（需要 Go 1.22+ 和 zip）
bash scripts/build.sh        # 产物：Tool.exe
python3 scripts/verify.py Tool.exe

# 3. 提交并打 tag，CI 自动发 Release
git add -A && git commit -m "feat: 初始化"
git tag v1.0.0 && git push origin main --tags
```

CI 触发方式：push 到 `main`/`master` 只出构建产物；打 `v*` tag 会额外发布 GitHub Release（附 `.sha256`）。

## 可配置项

| 变量 | 默认值 | 说明 |
|---|---|---|
| `OUT_NAME` | `Tool.exe` | 产物文件名（建议 ASCII） |
| `ENTRY` | `windows/app.exe` | Windows 端解压后运行的入口 |
| `STUB_ARCH` | `amd64` | 引导程序架构，32 位改 `386` |
| `MARKER` | `===SFX-PAYLOAD-2F7C9A31===` | 引导程序与负载之间的分隔标记 |

在 `.github/workflows/build.yml` 的 `env:` 里改即可；本地构建用同名环境变量覆盖。

## 原理

```
Tool.exe = [PE 引导程序 stub] + [marker] + [ZIP 负载]
```

Windows 只认开头的 PE；ZIP 的目录信息在文件尾部，所以同一个文件既能被 Windows 执行，
又能被 7-Zip / WinRAR / ZArchiver / MT管理器 当作压缩包打开（这类"前置数据"绝大多数解压工具都支持）。

## 兼容性

| 平台 | 支持情况 | 用户操作 |
|---|---|---|
| Windows 7 SP1 / 8 / 10 / 11（32 位、64 位、ARM64） | ✅ 双击即用 | 无需操作 |
| Android 4.0+ | ✅ | 改后缀为 `.zip`，用 ZArchiver / MT管理器 / RAR 解压 |
| macOS / Linux | ✅ | 改后缀为 `.zip` 解压 |
| iOS / iPadOS | ⚠️ 需签名渠道 | 解压取出 `.ipa`，用 AltStore / 企业签 / TestFlight 安装 |

**为兼容性做的取舍**

- 引导程序按 **32 位（GOARCH=386）** 编译：一个二进制同时兼容 32/64 位 Windows，ARM64 也能模拟运行
- Go 固定 **1.20.x**：最后一个支持 Windows 7/8 的版本；只面向 Win10+ 可升到最新
- 负载用 **ZIP**（而非 7z）：Windows / Android / macOS 的通用解压工具都能识别
- `使用说明.txt` 打包时自动转为 **UTF-8 BOM + CRLF**：老版本 Windows 记事本也能正常显示中文
- 包内目录名保持 **ASCII**（`windows/` `android/` …），避免文件名编码问题
- 单文件超过 **4 GiB** 会启用 ZIP64，个别老旧解压工具不支持（构建时会给出提示）
- 解压目录优先用系统临时目录，不可写时自动退回 exe 同目录的 `Tool-data/`

**排障**

Windows 上双击没反应时，可命令行执行：

```bat
Tool.exe --sfx-extract D:\out
```

只解压不运行，用于确认包是否完整。

## 常见问题

**Q：杀软 / SmartScreen 报毒怎么办？**
自解压包天然敏感，自写 stub 误报率高于 7-Zip/WinRAR 官方 stub。建议给**内层** `app.exe` 做代码签名。
注意：**不要**用 signtool 签最终产物，Authenticode 签名追加在文件末尾，会破坏 ZIP 结构。

**Q：payloads 太大，git push 失败？**
GitHub 单文件硬上限 100 MB。启用 `.gitignore` 里的负载忽略规则，然后在 workflow 里用
`actions/download-artifact` 从其他构建任务拉取（`build.yml` 里已留注释模板），或使用 Git LFS。

**Q：产物太大，Release 传不上去？**
单个 Release 附件上限 2 GB。超了就按平台拆包，或只发安卓/Windows 两个包。

**Q：iOS 为什么还要单独一步？**
Apple 的签名与信任链规则，任何打包方式都绕不过；本工具只负责把 `.ipa` 送到用户手上。

**Q：安卓用户改后缀解压失败？**
部分系统自带文件管理器不支持"带前置数据"的 ZIP，请让用户用 ZArchiver / MT管理器 / RAR。

## 本地环境

- Go 1.22+
- `zip`（Linux：`apt install zip`；macOS 自带；Termux：`pkg install zip`）
- Python 3（仅校验脚本用）

## License

MIT
