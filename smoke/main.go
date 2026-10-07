// 冒烟测试用的假入口程序。
//
// 被引导程序解压并启动后，它把一段文字写进 SFX_SMOKE_OUT 指定的文件，
// CI 据此断言"自解压 + 启动入口"这条链路真的跑通了。
package main

import (
	"fmt"
	"os"
	"path/filepath"
)

func main() {
	out := os.Getenv("SFX_SMOKE_OUT")
	if out == "" {
		out = filepath.Join(os.TempDir(), "sfx-smoke-ok.txt")
	}

	wd, err := os.Getwd()
	if err != nil {
		wd = "?"
	}
	msg := fmt.Sprintf("ok\ncwd=%s\nargs=%v\n", wd, os.Args)

	if err := os.WriteFile(out, []byte(msg), 0o644); err != nil {
		fmt.Fprintln(os.Stderr, "写标记文件失败:", err)
		os.Exit(1)
	}
	fmt.Print(msg)
}
