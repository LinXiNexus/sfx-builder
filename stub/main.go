//go:build windows

// 引导程序：定位自身文件尾部的压缩包 -> 解压 -> 运行入口程序。
//
// 排障用法（命令行）：
//
//	Tool.exe --sfx-extract [目标目录]     只解压不运行
//
// markerStr / entryPath 由 scripts/build.sh 通过 -ldflags "-X main.xxx=yyy" 注入。
package main

import (
	"archive/zip"
	"bytes"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"unsafe"
)

var (
	markerStr = "===SFX-PAYLOAD-2F7C9A31==="
	entryPath = "windows/app.exe"
)

func main() {
	if err := run(); err != nil {
		msgBox("启动失败：\n" + err.Error())
		os.Exit(1)
	}
}

func run() error {
	zr, err := openPayload()
	if err != nil {
		return err
	}
	args := os.Args[1:]

	// 排障用法：只解压不运行
	if len(args) > 0 && args[0] == "--sfx-extract" {
		out := filepath.Join(filepath.Dir(selfPath()), "Tool-data")
		if len(args) > 1 {
			out = args[1]
		}
		if err := os.MkdirAll(out, 0o755); err != nil {
			return err
		}
		if err := extractAll(zr, out); err != nil {
			return err
		}
		msgBox("已解压到：\n" + out)
		return nil
	}

	dir, err := workDir()
	if err != nil {
		return err
	}
	if err := extractAll(zr, dir); err != nil {
		return err
	}

	target := filepath.Join(dir, filepath.FromSlash(entryPath))
	if _, err := os.Stat(target); err != nil {
		msgBox("已解压到：\n" + dir + "\n\n但未找到入口程序 " + entryPath)
		return nil
	}

	cmd := exec.Command(target, args...)
	cmd.Dir = filepath.Dir(target)
	return cmd.Run()
}

// openPayload 读取自身文件，定位内嵌的 ZIP 负载。
func openPayload() (*zip.Reader, error) {
	blob, err := os.ReadFile(selfPath())
	if err != nil {
		return nil, err
	}
	marker := []byte(markerStr)
	// 用 marker + ZIP 本地文件头 "PK\x03\x04" 定位负载：
	// 即使引导程序自己的二进制里出现同样的 marker 字符串也不会误判。
	needle := append(append([]byte{}, marker...), 'P', 'K', 3, 4)
	i := bytes.Index(blob, needle)
	if i < 0 {
		return nil, fmt.Errorf("未找到内置负载（文件可能被截断或被安全软件改写）")
	}
	payload := blob[i+len(marker):]
	zr, err := zip.NewReader(bytes.NewReader(payload), int64(len(payload)))
	if err != nil {
		return nil, fmt.Errorf("负载损坏：%w", err)
	}
	return zr, nil
}

// workDir 优先使用系统临时目录；不可写时退回 exe 同目录的 Tool-data/。
func workDir() (string, error) {
	if d, err := os.MkdirTemp("", "sfx-"); err == nil {
		return d, nil
	}
	base := filepath.Join(filepath.Dir(selfPath()), "Tool-data")
	if err := os.MkdirAll(base, 0o755); err != nil {
		return "", err
	}
	return os.MkdirTemp(base, "sfx-")
}

func selfPath() string {
	self, err := os.Executable()
	if err != nil {
		return "."
	}
	return self
}

func extractAll(zr *zip.Reader, dir string) error {
	root := filepath.Clean(dir)
	for _, f := range zr.File {
		p := filepath.Join(root, filepath.FromSlash(f.Name))
		if p != root && !strings.HasPrefix(p, root+string(os.PathSeparator)) {
			continue // 防 zip-slip
		}
		if f.FileInfo().IsDir() {
			if err := os.MkdirAll(p, 0o755); err != nil {
				return err
			}
			continue
		}
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			return err
		}
		if err := writeFile(p, f); err != nil {
			return err
		}
	}
	return nil
}

func writeFile(p string, f *zip.File) error {
	rc, err := f.Open()
	if err != nil {
		return err
	}
	defer rc.Close()
	out, err := os.Create(p)
	if err != nil {
		return err
	}
	defer out.Close()
	_, err = io.Copy(out, rc)
	return err
}

// msgBox 弹系统提示框，避免"双击后一闪而过"用户不知道发生了什么。
func msgBox(text string) {
	u := syscall.NewLazyDLL("user32.dll")
	p := u.NewProc("MessageBoxW")
	t, _ := syscall.UTF16PtrFromString(text)
	c, _ := syscall.UTF16PtrFromString("提示")
	p.Call(0, uintptr(unsafe.Pointer(t)), uintptr(unsafe.Pointer(c)), 0x40)
}
