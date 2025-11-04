$paths = @("storage\api.pid","storage\ui.pid")
foreach ($p in $paths) {
  if (Test-Path $p) {
    $procId = Get-Content $p | Select-Object -First 1
    if ($procId) { Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue }
    Remove-Item $p -ErrorAction SilentlyContinue
  }
}
Write-Output "Stopped."
