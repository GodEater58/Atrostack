// Windows GUI launcher for the self-contained portable distribution.
package main

import (
    "fmt"
    "os"
    "os/exec"
    "path/filepath"
    "syscall"
    "unsafe"
)

func showError(message string) {
    title, _ := syscall.UTF16PtrFromString("AstroStack")
    text, _ := syscall.UTF16PtrFromString(message)
    syscall.NewLazyDLL("user32.dll").NewProc("MessageBoxW").Call(
        0, uintptr(unsafe.Pointer(text)), uintptr(unsafe.Pointer(title)), 0x10)
}

func main() {
    exe, err := os.Executable()
    if err != nil { showError(err.Error()); os.Exit(1) }
    root := filepath.Dir(exe)
    py := filepath.Join(root, "runtime", "pythonw.exe")
    app := filepath.Join(root, "app", "main.py")
    for _, path := range []string{py, app} {
        if _, err := os.Stat(path); err != nil {
            showError("Il pacchetto AstroStack non e completo. Estrai tutto lo ZIP e mantieni le cartelle app e runtime accanto ad AstroStack.exe.\n\n" + path)
            os.Exit(1)
        }
    }
    args := append([]string{app}, os.Args[1:]...)
    cmd := exec.Command(py, args...)
    cmd.Dir = filepath.Join(root, "app")
    cmd.Env = append(os.Environ(), "PYTHONNOUSERSITE=1", "PYTHONDONTWRITEBYTECODE=1")
    cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000}
    logRoot := os.Getenv("LOCALAPPDATA")
    if logRoot == "" { logRoot = os.TempDir() }
    logDir := filepath.Join(logRoot, "AstroStack", "logs")
    if err := os.MkdirAll(logDir, 0755); err == nil {
        log, err := os.OpenFile(filepath.Join(logDir, "launcher.log"), os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
        if err == nil { defer log.Close(); cmd.Stdout = log; cmd.Stderr = log }
    }
    if err := cmd.Start(); err != nil {
        showError(fmt.Sprintf("Avvio di AstroStack non riuscito.\n\n%v\n\nLog: %s", err, logDir))
        os.Exit(1)
    }
    // Python's GUI process runs independently; no console is created.
    _ = cmd.Process.Release()
}
