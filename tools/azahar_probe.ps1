# azahar_probe.ps1 -Rom <.cci> -Name <short> [-Seconds 150] [-Every 15] [-Filter "<log filter>"]: starts
# a 3DS game in Azahar (portable: its user folder next to azahar.exe, %APPDATA% untouched), muted,
# without the update check, and saves its window every few seconds (PrintWindow, both screens as
# Azahar lays them out) plus its log into runs\3ds\<Name>. Then closes it. Input: none.
param([Parameter(Mandatory = $true)][string]$Rom, [Parameter(Mandatory = $true)][string]$Name,
      [int]$Seconds = 150, [int]$Every = 15,
      [string]$Filter = "*:Info Service.IR:Trace Service.NFC:Debug Service.APT:Debug",
      [string]$Azahar = (Join-Path $env:LOCALAPPDATA "SkylandersDev\3ds\azahar-2126.2\azahar-windows-msvc-2126.2"),
      [string]$Out = "")
$dev = Join-Path $env:LOCALAPPDATA "SkylandersDev"
$az = $Azahar
$ini = Join-Path $az "user\config\qt-config.ini"
$out = if ($Out) { $Out } else { Join-Path $dev "runs\3ds\$Name" }
New-Item -ItemType Directory -Force $out | Out-Null

# Settings: muted, no update check, no first-start dialog, the log filter.
$text = [IO.File]::ReadAllText($ini)
foreach ($kv in @(@('volume', '0'), @('check_for_update_on_start', 'false'), @('firstStart', 'false'), @('log_filter', $Filter))) {
  $k = [regex]::Escape($kv[0])
  $text = [regex]::Replace($text, "(?m)^$k\\default=true\r?$", "$($kv[0])\default=false")
  $text = [regex]::Replace($text, "(?m)^$k=[^\r\n]*", "$($kv[0])=$($kv[1])")
}
[IO.File]::WriteAllText($ini, $text, (New-Object Text.UTF8Encoding($false)))

Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public static class AzWin {
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
}
"@
function Save-Shot([System.Diagnostics.Process]$p, [string]$file) {
  $p.Refresh()
  $h = $p.MainWindowHandle
  if ($h -eq [IntPtr]::Zero) { return "no window" }
  $r = New-Object AzWin+RECT
  [AzWin]::GetClientRect($h, [ref]$r) | Out-Null
  $w = [math]::Max(1, $r.R - $r.L); $hh = [math]::Max(1, $r.B - $r.T)
  $bmp = New-Object System.Drawing.Bitmap $w, $hh
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $hdc = $g.GetHdc()
  [AzWin]::PrintWindow($h, $hdc, 3) | Out-Null
  $g.ReleaseHdc($hdc); $g.Dispose()
  $bmp.Save($file, [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
  return "$($w)x$($hh)"
}

$log = Join-Path $az "user\log\azahar_log.txt"
$p = Start-Process -FilePath (Join-Path $az "azahar.exe") -ArgumentList "`"$Rom`"" -WorkingDirectory $az -PassThru
$t0 = Get-Date
$n = 0
while (((Get-Date) - $t0).TotalSeconds -lt $Seconds -and -not $p.HasExited) {
  Start-Sleep -Seconds $Every
  if ($p.HasExited) { break }
  $n++
  $sec = [int]((Get-Date) - $t0).TotalSeconds
  $size = Save-Shot $p (Join-Path $out ("{0:D2}_{1:D3}s.png" -f $n, $sec))
  "shot $n at $sec s ($size), title: $($p.MainWindowTitle)"
}
$exited = $p.HasExited
if (-not $exited) { Stop-Process -Id $p.Id -Force -Confirm:$false }
Start-Sleep -Milliseconds 800
if (Test-Path $log) { Copy-Item $log (Join-Path $out "azahar_log.txt") -Force }
"done: $n shots, exited by itself: $exited, log $((Get-Item (Join-Path $out 'azahar_log.txt') -ErrorAction SilentlyContinue).Length) bytes"
