docker compose down
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'barabari-mentoring-platform' -and $_.Name -match 'java|node|python' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

