# azahar_taps.ps1 -Rom <.cci> -Name <short> -Taps "60:950,660;75:950,660" [-Keys "90:A"] [-Seconds 150] [-Every 10]:
# like azahar_probe.ps1, plus taps on the window (seconds:x,y in its client area, as on the probe's
# screenshots) and keys (seconds:<Azahar key>), posted to Azahar's own windows (PostMessage), so
# nothing lands in another program and the mouse stays where it is.
param([Parameter(Mandatory = $true)][string]$Rom, [Parameter(Mandatory = $true)][string]$Name,
      [string]$Taps = "", [string]$Keys = "", [int]$Seconds = 150, [int]$Every = 10,
      [string]$Filter = "*:Info Service.IR:Trace Service.NFC:Debug",
      [string]$Azahar = (Join-Path $env:LOCALAPPDATA "SkylandersDev\3ds\azahar-2126.2\azahar-windows-msvc-2126.2"),
      [string]$Out = "")
$dev = Join-Path $env:LOCALAPPDATA "SkylandersDev"
$az = $Azahar
$ini = Join-Path $az "user\config\qt-config.ini"
$out = if ($Out) { $Out } else { Join-Path $dev "runs\3ds\$Name" }
New-Item -ItemType Directory -Force $out | Out-Null
$text = [IO.File]::ReadAllText($ini)
foreach ($kv in @(@('volume', '0'), @('check_for_update_on_start', 'false'), @('firstStart', 'false'), @('confirmClose', 'false'), @('log_filter', $Filter))) {
  $k = [regex]::Escape($kv[0])
  $text = [regex]::Replace($text, "(?m)^$k\\default=true\r?$", "$($kv[0])\default=false")
  $text = [regex]::Replace($text, "(?m)^$k=[^\r\n]*", "$($kv[0])=$($kv[1])")
}
[IO.File]::WriteAllText($ini, $text, (New-Object Text.UTF8Encoding($false)))

Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices; using System.Collections.Generic;
public static class AzIn {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
  [DllImport("user32.dll")] public static extern bool ScreenToClient(IntPtr h, ref POINT p);
  [DllImport("user32.dll")] public static extern IntPtr ChildWindowFromPointEx(IntPtr h, POINT p, uint flags);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint code, uint type);
  [DllImport("user32.dll")] public static extern IntPtr GetParent(IntPtr h);
  // The deepest child window under a client point of top (skipping invisible/disabled ones), and
  // the point in that child's client coordinates.
  public static IntPtr Deepest(IntPtr top, int x, int y, out int cx, out int cy) {
    POINT s = new POINT { X = x, Y = y };
    ClientToScreen(top, ref s);
    IntPtr cur = top;
    while (true) {
      POINT c = s; ScreenToClient(cur, ref c);
      IntPtr next = ChildWindowFromPointEx(cur, c, 1 | 2);
      if (next == IntPtr.Zero || next == cur) { cx = c.X; cy = c.Y; return cur; }
      cur = next;
    }
  }
  public static IntPtr L(int x, int y) { return (IntPtr)((y << 16) | (x & 0xFFFF)); }
}
"@
function Save-Shot([System.Diagnostics.Process]$p, [string]$file) {
  $p.Refresh(); $h = $p.MainWindowHandle
  if ($h -eq [IntPtr]::Zero) { return "no window" }
  $r = New-Object AzIn+RECT; [AzIn]::GetClientRect($h, [ref]$r) | Out-Null
  $bmp = New-Object System.Drawing.Bitmap ([math]::Max(1, $r.R)), ([math]::Max(1, $r.B))
  $g = [System.Drawing.Graphics]::FromImage($bmp); $hdc = $g.GetHdc()
  [AzIn]::PrintWindow($h, $hdc, 3) | Out-Null
  $g.ReleaseHdc($hdc); $g.Dispose(); $bmp.Save($file, [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
}
function Tap([System.Diagnostics.Process]$p, [int]$x, [int]$y) {
  $p.Refresh(); $top = $p.MainWindowHandle
  $cx = 0; $cy = 0
  $w = [AzIn]::Deepest($top, $x, $y, [ref]$cx, [ref]$cy)
  # Azahar's OpenGL surface can be a native window one window frame larger than the render widget
  # around it (+16 x +39 px at 96 dpi, placed 8 px left and 31 px up). The picture is drawn at the
  # surface's bottom left in the widget's size, but a click is read from the surface's top: without
  # this, a tap lands that many pixels lower than drawn (a tap on English picked French, 2026-11-12).
  $parent = [AzIn]::GetParent($w)
  if ($parent -ne [IntPtr]::Zero -and $parent -ne $top) {
    $rw = New-Object AzIn+RECT; [AzIn]::GetClientRect($w, [ref]$rw) | Out-Null
    $rp = New-Object AzIn+RECT; [AzIn]::GetClientRect($parent, [ref]$rp) | Out-Null
    if ($rw.B -gt $rp.B) { $cy -= ($rw.B - $rp.B) }
  }
  [AzIn]::PostMessage($w, 0x0200, [IntPtr]0, [AzIn]::L($cx, $cy)) | Out-Null   # WM_MOUSEMOVE
  [AzIn]::PostMessage($w, 0x0201, [IntPtr]1, [AzIn]::L($cx, $cy)) | Out-Null   # WM_LBUTTONDOWN
  Start-Sleep -Milliseconds 120
  [AzIn]::PostMessage($w, 0x0202, [IntPtr]0, [AzIn]::L($cx, $cy)) | Out-Null   # WM_LBUTTONUP
  "tap $x,$y -> window 0x$('{0:X}' -f [int64]$w) at $cx,$cy"
}
function Key([System.Diagnostics.Process]$p, [string]$name) {
  $p.Refresh(); $top = $p.MainWindowHandle
  $cx = 0; $cy = 0
  $w = [AzIn]::Deepest($top, 850, 360, [ref]$cx, [ref]$cy)
  # A letter or digit, or F1..F12 (Azahar's own shortcuts: F10 the next screen layout, F8 upright).
  $vk = if ($name -match '^[Ff](\d{1,2})$') { 0x6F + [int]$Matches[1] } else { [int][char]$name.ToUpper()[0] }
  $scan = [AzIn]::MapVirtualKey([uint32]$vk, 0)
  [AzIn]::PostMessage($w, 0x0100, [IntPtr]$vk, [IntPtr](1 -bor ($scan -shl 16))) | Out-Null           # WM_KEYDOWN
  Start-Sleep -Milliseconds 150
  [AzIn]::PostMessage($w, 0x0101, [IntPtr]$vk, [IntPtr](1 -bor ($scan -shl 16) -bor (3 -shl 30))) | Out-Null  # WM_KEYUP
  "key $name -> window 0x$('{0:X}' -f [int64]$w)"
}
$events = @()
foreach ($t in ($Taps -split ';' | Where-Object { $_ })) { $a = $t -split ':'; $xy = $a[1] -split ','; $events += [pscustomobject]@{ at = [int]$a[0]; kind = 'tap'; x = [int]$xy[0]; y = [int]$xy[1]; key = '' } }
foreach ($k in ($Keys -split ';' | Where-Object { $_ })) { $a = $k -split ':'; $events += [pscustomobject]@{ at = [int]$a[0]; kind = 'key'; x = 0; y = 0; key = $a[1] } }
$events = @($events | Sort-Object at)
$log = Join-Path $az "user\log\azahar_log.txt"
$p = Start-Process -FilePath (Join-Path $az "azahar.exe") -ArgumentList "`"$Rom`"" -WorkingDirectory $az -PassThru
$t0 = Get-Date; $nextShot = $Every; $n = 0; $ei = 0
while (((Get-Date) - $t0).TotalSeconds -lt $Seconds -and -not $p.HasExited) {
  Start-Sleep -Milliseconds 250
  $sec = ((Get-Date) - $t0).TotalSeconds
  while ($ei -lt $events.Count -and $events[$ei].at -le $sec) {
    $e = $events[$ei]; $ei++
    if ($e.kind -eq 'tap') { Tap $p $e.x $e.y } else { Key $p $e.key }
    Start-Sleep -Milliseconds 700
    $n++; Save-Shot $p (Join-Path $out ("{0:D2}_{1:D3}s_after_{2}.png" -f $n, [int]$sec, $e.kind))
  }
  if ($sec -ge $nextShot) { $n++; Save-Shot $p (Join-Path $out ("{0:D2}_{1:D3}s.png" -f $n, [int]$sec)); $nextShot += $Every }
}
$exited = $p.HasExited
# Closed like a player would (the log is written out then), and only killed if that hangs.
if (-not $exited) { $p.CloseMainWindow() | Out-Null; if (-not $p.WaitForExit(15000)) { Stop-Process -Id $p.Id -Force -Confirm:$false } }
Start-Sleep -Milliseconds 800
if (Test-Path $log) { Copy-Item $log (Join-Path $out "azahar_log.txt") -Force }
"done: $n shots, exited by itself: $exited"
