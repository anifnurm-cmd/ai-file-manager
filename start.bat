@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================
echo        AI FILE MANAGER
 echo ========================================
echo.
where py >nul 2>&1 || (echo Python Launcher not found. Install Python 3.13+ and enable the launcher.& pause& exit /b 1)
if not exist ".venv\Scripts\python.exe" (
  echo Creating Python 3.13 virtual environment...
  py -3.13 -m venv .venv || (echo ERROR: Python 3.13 is required.& pause& exit /b 1)
)
call ".venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (echo ERROR: pip upgrade failed.& pause& exit /b 1)
call ".venv\Scripts\python.exe" -m pip install --prefer-binary -r requirements.txt
if errorlevel 1 (echo ERROR: dependency installation failed.& pause& exit /b 1)
call ".venv\Scripts\python.exe" -m pip check
if errorlevel 1 (echo ERROR: dependency conflict detected.& pause& exit /b 1)
call ".venv\Scripts\python.exe" -m py_compile app.py
if errorlevel 1 (echo ERROR: application failed compilation.& pause& exit /b 1)
echo Starting server...
start "AI File Manager Server" cmd /k "cd /d ""%~dp0"" && .venv\Scripts\python.exe app.py"
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:8787"
exit /b 0
