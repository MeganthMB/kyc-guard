@echo off
REM One-click start for Windows. First run creates a virtual env and installs packages.
cd /d "%~dp0"
if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv || (echo Python 3.10+ is required: https://www.python.org/downloads/ & pause & exit /b 1)
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt || (pause & exit /b 1)
    python -m core.seed
) else (
    call .venv\Scripts\activate.bat
)
start "" cmd /c "timeout /t 6 /nobreak >nul & start http://localhost:8501"
streamlit run app.py
