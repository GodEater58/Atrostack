package main

import (
    _ "embed"
    "os"
    "os/exec"
    "path/filepath"
    "syscall"
)

//go:embed payload.zip
var payload []byte

//go:embed install_offline.ps1
var installerPS []byte

func write(path string, data []byte) error {
    return os.WriteFile(path, data, 0600)
}

func run() int {
    dir, err := os.MkdirTemp("", "AstroStack-Offline-Setup-*")
    if err != nil { return 1 }
    defer os.RemoveAll(dir)

    zipPath := filepath.Join(dir, "payload.zip")
    psPath := filepath.Join(dir, "install_offline.ps1")

    if write(zipPath, payload) != nil { return 1 }
    if write(psPath, installerPS) != nil { return 1 }

    args := []string{ "-NoProfile", "-ExecutionPolicy", "Bypass", "-STA",
        "-WindowStyle", "Hidden", "-File", psPath,
        "-PayloadZip", zipPath,
    }
    if len(os.Args) == 2 && os.Args[1] == "-Silent" { args = append(args, "-Silent") }
    cmd := exec.Command("powershell.exe", args...)
    cmd.Dir = dir
    cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
    if err := cmd.Run(); err != nil { return 1 }
    return 0
}

func main() { os.Exit(run()) }
