<#
invoice_edenstar_scheduled.ps1 — wrapper สำหรับ scheduled task งาน 請求書 ザ エディスターホテル成田

รอบงาน (ตาม king-bus-taicho-sop.md):
  - วันที่ 16 ของเดือน -> 前半 (1-15)  => --half front, --month = เดือนปัจจุบัน
  - วันที่ 1 ของเดือน  -> 後半 (16-สิ้นเดือน) => --half back, --month = เดือนที่แล้ว

ส่ง --skip-if-exists เสมอ: ถ้าไฟล์ output มีอยู่แล้ว script จะข้าม (ไม่ทับไฟล์ที่สร้าง/แก้มือ)
+ แจ้ง Discord #ai-activity-log (ผ่าน script เอง)
log ไป %USERPROFILE%\.config\opencode\logs\invoice_edenstar_<half>_<timestamp>.log

ตัวอย่าง:
  powershell -ExecutionPolicy Bypass -File <path>\invoice_edenstar_scheduled.ps1 -Half back
  powershell -ExecutionPolicy Bypass -File <path>\invoice_edenstar_scheduled.ps1 -Half front -DryRun
#>
param(
    [Parameter(Mandatory = $true)][ValidateSet("front", "back")] [string] $Half,
    [switch] $DryRun,
    [int] $Month = 0
)
$ErrorActionPreference = "Stop"

$today = Get-Date
if ($Month -gt 0) { $month = $Month } elseif ($Half -eq "front") { $month = $today.Month } else { $month = $today.AddMonths(-1).Month }

$scriptPath = "D:\GitHub\senei-kotsu-invoice\tools\invoice_edenstar.py"
$logDir = Join-Path $env:USERPROFILE ".config\opencode\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ("invoice_edenstar_{0}_{1}.log" -f $Half, (Get-Date -Format "yyyyMMdd_HHmmss"))

$pyArgs = @($scriptPath, "--month", "$month", "--half", $Half, "--skip-if-exists")
if ($DryRun) { $pyArgs += "--dry-run" }

Write-Host "== invoice_edenstar_scheduled: half=$Half month=$month dryrun=$DryRun =="
& python @pyArgs 2>&1 | Tee-Object -FilePath $logFile
$code = $LASTEXITCODE
Write-Host "exit=$code log=$logFile"
exit $code
