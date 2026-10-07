# payloads

把各平台产物按下面的结构放进来，构建时会原样打进单文件里。

```
payloads/
├── windows/app.exe
├── android/app.apk
├── ios/App.ipa
├── mac/你的.app 或 .dmg
└── linux/你的程序（AppImage 等）
```

- 入口程序路径由环境变量 `ENTRY` 指定，默认 `windows/app.exe`，请保持一致。
- 二进制默认入库；如果体积大（GitHub 单文件推送上限 100 MB），
  请启用 `.gitignore` 里注释掉的规则，改用 CI 的 `download-artifact` 拉取（见根目录 README）。
