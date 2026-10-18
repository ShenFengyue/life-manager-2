# Dev helper: launch the app and capture real window screenshots for visual review.
# ASCII-only on purpose: Windows PowerShell 5.1 reads .ps1 files as ANSI.
param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot),
    [string]$OutDir,
    [int]$WaitSeconds = 8,
    [switch]$SwitchPages
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms, System.Drawing

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32 {
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
}
"@

if (-not $OutDir) { $OutDir = Join-Path $Root ".preview\live" }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$exe = Join-Path $Root ".venv\Scripts\pythonw.exe"
$entry = Join-Path $Root "app\main.py"

$process = Start-Process -FilePath $exe -ArgumentList $entry -WorkingDirectory $Root -PassThru
Start-Sleep -Seconds $WaitSeconds

function Get-WindowHandle($proc) {
    for ($i = 0; $i -lt 20; $i++) {
        $proc.Refresh()
        if ($proc.MainWindowHandle -ne [IntPtr]::Zero) { return $proc.MainWindowHandle }
        Start-Sleep -Milliseconds 500
    }
    return [IntPtr]::Zero
}

function Save-WindowShot($handle, $path) {
    $rect = New-Object Win32+RECT
    [void][Win32]::GetWindowRect($handle, [ref]$rect)
    $width = $rect.Right - $rect.Left
    $height = $rect.Bottom - $rect.Top
    if ($width -le 0 -or $height -le 0) { throw "Invalid window size: $width x $height" }
    $bitmap = New-Object System.Drawing.Bitmap $width, $height
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0, $bitmap.Size)
    $bitmap.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $graphics.Dispose()
    $bitmap.Dispose()
    Write-Output "captured $path ($width x $height)"
}

$handle = Get-WindowHandle $process
if ($handle -eq [IntPtr]::Zero) {
    Write-Output "no application window found (process may have exited)"
    exit 1
}

[void][Win32]::SetForegroundWindow($handle)
Start-Sleep -Milliseconds 1200
Save-WindowShot $handle (Join-Path $OutDir "window.png")

if ($SwitchPages) {
    $pages = @{ 1 = "overview"; 2 = "processes"; 3 = "heatmaps"; 4 = "activity"; 5 = "data" }
    foreach ($key in 1..5) {
        [void][Win32]::SetForegroundWindow($handle)
        Start-Sleep -Milliseconds 400
        [System.Windows.Forms.SendKeys]::SendWait("^$key")
        Start-Sleep -Milliseconds 1500
        Save-WindowShot $handle (Join-Path $OutDir ("page-{0}-{1}.png" -f $key, $pages[$key]))
    }
}

Write-Output "app still running (PID $($process.Id))"
