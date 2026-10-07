//go:build !windows

package main

import "fmt"

func main() {
	fmt.Println("引导程序只在 Windows 上运行；构建时请使用 GOOS=windows。")
}
