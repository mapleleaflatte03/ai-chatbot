Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
chcp 65001 > $null

$API_PORT = if ($env:API_PORT) { $env:API_PORT } else { "8000" }
$UI_PORT  = if ($env:UI_PORT)  { $env:UI_PORT  } else { "8501" }
$BACKEND  = "http://127.0.0.1:$API_PORT"

if (!(Test-Path .venv)) { python -m venv .venv }
$py  = ".\.venv\Scripts\python.exe"
$pip = ".\.venv\Scripts\pip.exe"

& $pip install --upgrade pip
& $pip install --only-binary :all: -r requirements.txt

New-Item -ItemType Directory -Force -Path data,storage | Out-Null

if (!(Test-Path data\faq.csv) -or ((Get-Content data\faq.csv -TotalCount 2).Count -lt 2)) {
  & $py scripts\01_crawl.py --seeds $env:DEMO_SEEDS --limit 80 --out data\faq.csv
}

if (!(Test-Path storage\index.faiss)) {
  & $py scripts\02_build_index.py --csv data\faq.csv --out storage\index.faiss --meta storage\meta.json
}

$apiArgs = @("app.main:app","--port",$API_PORT)
Start-Process -FilePath ".\.venv\Scripts\uvicorn.exe" -ArgumentList $apiArgs -WindowStyle Hidden -PassThru |
  Select-Object -ExpandProperty Id | Out-File storage\api.pid -Encoding ascii

$env:BACKEND = $BACKEND
$uiArgs = @("run","ui\app.py","--server.port",$UI_PORT,"--server.headless","true")
Start-Process -FilePath ".\.venv\Scripts\streamlit.exe" -ArgumentList $uiArgs -WindowStyle Hidden -PassThru |
  Select-Object -ExpandProperty Id | Out-File storage\ui.pid -Encoding ascii

# wait API
$ok = $false
for ($i=0; $i -lt 30 -and -not $ok; $i++) {
  Start-Sleep -Seconds 1
  try { if ((Invoke-RestMethod -Uri "http://127.0.0.1:$API_PORT/health" -TimeoutSec 2).ok) { $ok = $true } } catch {}
}

# wait UI
$u = $false
for ($i=0; $i -lt 30 -and -not $u; $i++) {
  Start-Sleep -Seconds 1
  try { if ((Invoke-WebRequest -Uri "http://127.0.0.1:$UI_PORT" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200) { $u = $true } } catch {}
}

# smoke queries (UTF-8)
$qs = @("Chính sách bảo hành?","Hướng dẫn sử dụng?","Giá/price?")
foreach ($q in $qs) {
  $b = ("{0}{1}{2}" -f '{"question":"', $q.Replace('"','\"'), '"}')
  try { Invoke-RestMethod -Uri "http://127.0.0.1:$API_PORT/ask" -Method Post -Body $b -ContentType "application/json; charset=utf-8" | Out-Null } catch {}
}

Write-Output ("API http://127.0.0.1:{0}" -f $API_PORT)
Write-Output ("UI  http://127.0.0.1:{0}" -f $UI_PORT)
