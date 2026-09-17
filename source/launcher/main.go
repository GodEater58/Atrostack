package main

import (
    "os"
    "os/exec"
    "path/filepath"
    "syscall"
    "unsafe"
)

const createNoWindow = 0x08000000

var (
    user32      = syscall.NewLazyDLL("user32.dll")
    messageBoxW = user32.NewProc("MessageBoxW")
)

func showError(message string) {
    title, _ := syscall.UTF16PtrFromString("AstroStack")
    text, _ := syscall.UTF16PtrFromString(message)
    messageBoxW.Call(
        0,
        uintptr(unsafe.Pointer(text)),
        uintptr(unsafe.Pointer(title)),
        0x10,
    )
}

func main() {
    exe, err := os.Executable()
    if err != nil {
        showError("Impossibile determinare la cartella di AstroStack.")
        return
    }

    root := filepath.Dir(exe)
    py := filepath.Join(root, "runtime", "pythonw.exe")
    app := filepath.Join(root, "app", "main.py")

    if _, err := os.Stat(py); err != nil {
        showError("Runtime Python privato non trovato. Riestrai completamente lo ZIP di AstroStack.")
        return
    }
    if _, err := os.Stat(app); err != nil {
        showError("File dell'applicazione non trovati. Riestrai completamente lo ZIP di AstroStack.")
        return
    }

    logDir := filepath.Join(root, "logs")
    _ = os.MkdirAll(logDir, 0755)
    logPath := filepath.Join(logDir, "AstroStack.log")
    logFile, _ := os.OpenFile(logPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
    if logFile != nil {
        defer logFile.Close()
    }

    args := []string{app}
    if len(os.Args) > 1 {
        args = append(args, os.Args[1:]...)
    }

    cmd := exec.Command(py, args...)
    cmd.Dir = filepath.Join(root, "app")
    cmd.Env = append(os.Environ(),
        "PYTHONNOUSERSITE=1",
        "PYTHONDONTWRITEBYTECODE=1",
        "PYTHONUTF8=1",
        "PYTHONIOENCODING=utf-8",
    )
    cmd.SysProcAttr = &syscall.SysProcAttr{
        HideWindow:    true,
        CreationFlags: createNoWindow,
    }
    if logFile != nil {
        cmd.Stdout = logFile
        cmd.Stderr = logFile
    }

    if err := cmd.Start(); err != nil {
        showError("AstroStack non è riuscito ad avviarsi. Controlla logs\\AstroStack.log oppure usa AstroStack-Debug.cmd.")
    }
}
