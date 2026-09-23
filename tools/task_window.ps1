<#
长任务窗口复用：查找 / 新建一个专用 PowerShell 窗口

为什么需要
----------
长任务（>2 分钟）必须开独立窗口跑，否则 run_commands 约 300 秒会超时
并杀掉进程。但每跑一次就开一个新窗口，窗口会越堆越多。

做法：给长任务窗口一个固定标题 "AIGC-TASK"，启动前先找：
  找到了 -> 复用（把命令投进去）
  没找到 -> 新建

投命令的方式：PowerShell 没有"外部注入命令行"的公开接口，所以用约定的
输入文件：窗口里跑一个守候循环，轮询 $env:TEMP\aigc_task_cmd.ps1，
文件存在就执行并删除。调用方写文件即可 —— 这就是"复用"的落地。

用法
----
  powershell -ExecutionPolicy Bypass -File tools\task_window.ps1 -Run "<命令>"
  powershell -ExecutionPolicy Bypass -File tools\task_window.ps1 -Status
  powershell -ExecutionPolicy Bypass -File tools\task_window.ps1 -Close
#>
param(
    [string]$Run = "",
    [switch]$Status,
    [switch]$Close,
    [switch]$Daemon
)

$TITLE   = "AIGC-TASK"
$CMDFILE = Join-Path $env:TEMP "aigc_task_cmd.ps1"
$PIDFILE = Join-Path $env:TEMP "aigc_task_win.pid"

function Get-TaskWindow {
    # **只按 PID 文件判断**。
    #
    # 为什么不按窗口标题：本项目实测 `Get-Process ... MainWindowTitle` 在
    # Windows PowerShell 宿主下**恒为空**（10 个 powershell 进程全读不到标题），
    # 按标题匹配等于永远找不到 -> 每次都新建窗口（踩过的坑）。
    #
    # PID 文件由守候窗口自己在启动时写入（Daemon 分支），所以只要文件里
    # 的 PID 还活着，就说明窗口在。
    if (Test-Path $PIDFILE) {
        $saved = (Get-Content $PIDFILE -Raw -ErrorAction SilentlyContinue)
        if ($saved -and $saved.Trim()) {
            $p = Get-Process -Id ([int]$saved.Trim()) -ErrorAction SilentlyContinue
            if ($p) { return $p }
        }
    }
    return $null
}

function Set-TaskTitle {
    try {
        $Host.UI.RawUI.WindowTitle = $TITLE
    } catch { }
    # 再用 Win32 API 设一次（RawUI 在部分宿主不生效）
    try {
        Add-Type -Namespace W -Name U -MemberDefinition @"
[DllImport("kernel32.dll")] public static extern IntPtr GetConsoleWindow();
[DllImport("user32.dll")] public static extern bool SetWindowText(IntPtr h, string t);
"@ -ErrorAction SilentlyContinue
        $h = [W.U]::GetConsoleWindow()
        if ($h -ne [IntPtr]::Zero) { [W.U]::SetWindowText($h, $TITLE) | Out-Null }
    } catch { }
}

# ---------------------------------------------------------------- 守候模式
if ($Daemon) {
    Set-TaskTitle
    Set-Content -Path $PIDFILE -Value $PID -Encoding ascii
    Write-Host "[$TITLE] 长任务窗口就绪，等待命令投递..."
    Write-Host "[$TITLE] 关掉本窗口即退出"
    while ($true) {
        if (Test-Path $CMDFILE) {
            $cmd = Get-Content $CMDFILE -Raw -Encoding UTF8
            Remove-Item $CMDFILE -Force -ErrorAction SilentlyContinue
            if ($cmd -and $cmd.Trim()) {
                Write-Host ""
                Write-Host ("=" * 68)
                Write-Host "[$TITLE] 开始执行"
                Write-Host ("=" * 68)
                try { Invoke-Expression $cmd }
                catch { Write-Host "[$TITLE] 出错: $_" -ForegroundColor Red }
                Write-Host ""
                Write-Host "[$TITLE] 完成，等待下一条命令..."
            }
        }
        Start-Sleep -Milliseconds 700
    }
}

# ---------------------------------------------------------------- 查询
if ($Status) {
    $w = Get-TaskWindow
    if ($w) { Write-Host "在: PID=$($w.Id)" } else { Write-Host "无长任务窗口" }
    exit 0
}

# ---------------------------------------------------------------- 关闭
if ($Close) {
    $w = Get-TaskWindow
    if ($w) { Stop-Process -Id $w.Id -Force; Write-Host "已关闭 PID=$($w.Id)" }
    else { Write-Host "无长任务窗口" }
    Remove-Item $PIDFILE -Force -ErrorAction SilentlyContinue
    Remove-Item $CMDFILE -Force -ErrorAction SilentlyContinue
    exit 0
}

# ---------------------------------------------------------------- 投递
if ($Run) {
    $w = Get-TaskWindow
    if (-not $w) {
        # 新建前先清掉可能残留的 PID 文件，避免误判
        Remove-Item $PIDFILE -Force -ErrorAction SilentlyContinue
        Start-Process -FilePath "powershell.exe" -ArgumentList @(
            "-NoExit", "-ExecutionPolicy", "Bypass",
            "-File", $PSCommandPath, "-Daemon"
        )
        # 等**PID 文件出现**（守候窗口启动时写）。
        # 注意：不能等"找到窗口标题" —— 本环境读不到 MainWindowTitle，
        # 会永远等不到，从而重复新建窗口（踩过的坑）。
        $t0 = Get-Date
        while (-not (Test-Path $PIDFILE) -and
               ((Get-Date) - $t0).TotalSeconds -lt 20) {
            Start-Sleep -Milliseconds 200
        }
        if (-not (Test-Path $PIDFILE)) {
            Write-Host "[task_window] 新建窗口失败（PID 文件未出现）"
            exit 1
        }
        Start-Sleep -Milliseconds 300      # 等它进入守候循环
        $w = Get-TaskWindow
        Write-Host "[task_window] 已新建窗口 (PID=$($w.Id))"
    } else {
        Write-Host "[task_window] 复用已有窗口 (PID=$($w.Id))"
    }
    Set-Content -Path $CMDFILE -Value $Run -Encoding UTF8
    Write-Host "[task_window] 命令已投递"
    exit 0
}

Write-Host "用法: -Run '<命令>' | -Status | -Close | -Daemon"

