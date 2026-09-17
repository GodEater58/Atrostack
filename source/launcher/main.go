package main

import (
    "os"
    "os/exec"
    "path/filepath"
    "syscall"
)

func main() {
    exe, err := os.Executable()
    if err != nil { return }
    root := filepath.Dir(exe)
    py := filepath.Join(root, "runtime", "pythonw.exe")
    app := filepath.Join(root, "app", "main.py")

    args := []string{app}
    if len(os.Args) > 1 {
        args = append(args, os.Args[1:]...)
    }
    cmd := exec.Command(py, args...)
    cmd.Dir = filepath.Join(root, "app")
    cmd.Env = append(os.Environ(), "PYTHONNOUSERSITE=1", "PYTHONDONTWRITEBYTECODE=1")
    cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
    _ = cmd.Start()
}
