@echo off
REM Share the app from THIS laptop with a free public https link (Cloudflare Quick Tunnel).
REM No account needed. The link works only while this window stays open.
cd /d "%~dp0"

if not exist .venv (
    echo First-time setup: run run.bat once, close it, then run this file again.
    pause
    exit /b 1
)

where cloudflared >nul 2>nul
if errorlevel 1 (
    echo Installing cloudflared...
    winget install --id Cloudflare.cloudflared -e --accept-source-agreements --accept-package-agreements
    echo.
    echo Installed. Close this window and double-click run_public.bat again.
    pause
    exit /b 0
)

call .venv\Scripts\activate.bat
start "KYC Guard app" cmd /k streamlit run app.py --server.headless true --server.port 8501
echo Waiting for the app to start...
timeout /t 10 /nobreak >nul
echo.
echo ============================================================
echo  Your public link is the https://....trycloudflare.com URL
echo  printed below. Share it with the judges.
echo ============================================================
cloudflared tunnel --url http://localhost:8501
