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

//go:embed python-runtime.exe
var pythonRuntime []byte

//go:embed wheelhouse.zip
var wheelhouse []byte

func write(path string, data []byte) error {
    return os.WriteFile(path, data, 0600)
}

func main() {
    dir, err := os.MkdirTemp("", "AstroStack-Offline-Setup-*")
    if err != nil { return }
    defer os.RemoveAll(dir)

    zipPath := filepath.Join(dir, "payload.zip")
    psPath := filepath.Join(dir, "install_offline.ps1")
    pyPath := filepath.Join(dir, "python-runtime.exe")
    wheelsPath := filepath.Join(dir, "wheelhouse.zip")

    if write(zipPath, payload) != nil { return }
    if write(psPath, installerPS) != nil { return }
    if write(pyPath, pythonRuntime) != nil { return }
    if write(wheelsPath, wheelhouse) != nil { return }

    cmd := exec.Command(
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-STA",
        "-WindowStyle", "Hidden", "-File", psPath,
        "-PayloadZip", zipPath,
        "-PythonInstaller", pyPath,
        "-WheelhouseZip", wheelsPath,
    )
    cmd.Dir = dir
    cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
    _ = cmd.Run()
}
