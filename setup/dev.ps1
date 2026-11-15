# Start the API (port 8080) and the web app (port 3000) in two windows. Close the windows to stop them.
$Root = Split-Path -Parent $PSScriptRoot
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root\backend'; .\.venv\Scripts\uvicorn app.main:app --reload --port 8080"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root\frontend'; `$env:NEXT_PUBLIC_API_URL='http://127.0.0.1:8080'; npm run dev -- --port 3000"
Write-Host "API: http://127.0.0.1:8080/docs    Web: http://localhost:3000"
