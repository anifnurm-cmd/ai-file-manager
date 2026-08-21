@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================
echo        AI FILE MANAGER - STARTUP
echo ========================================
echo.

where py >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python Launcher 'py' was not found.
  echo Install Python 3.13 or later from https://www.python.org/downloads/windows/
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment with Python 3.13...
  py -3.13 -m venv .venv >nul 2>&1
  if errorlevel 1 (
    echo Python 3.13 was not found. Trying the default installed Python...
    py -m venv .venv
    if errorlevel 1 (
      echo ERROR: Could not create the Python virtual environment.
      echo.
      py --version
      echo.
      pause
      exit /b 1
    )
  )
)

echo Python version in virtual environment:
.venv\Scripts\python.exe --version

echo Installing / updating dependencies...
call ".venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
  echo ERROR: pip upgrade failed.
  echo Check your internet connection or corporate proxy settings.
  pause
  exit /b 1
)

call ".venv\Scripts\python.exe" -m pip install --prefer-binary -r requirements.txt
if errorlevel 1 (
  echo ERROR: dependency installation failed.
  echo The error above is the important part. Leave this window open.
  pause
  exit /b 1
)

call ".venv\Scripts\python.exe" -m pip check
if errorlevel 1 (
  echo ERROR: installed packages have dependency conflicts.
  pause
  exit /b 1
)

call ".venv\Scripts\python.exe" -m py_compile app.py
if errorlevel 1 (
  echo ERROR: application failed Python compilation.
  pause
  exit /b 1
)

echo.
echo Starting AI File Manager...
start "AI File Manager Server" cmd /k "cd /d ""%~dp0"" && .venv\Scripts\python.exe app.py"

timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:8787"

echo.
echo Browser opened at http://127.0.0.1:8787
 echo Keep the server window open while using the app.
echo.
exit /b 0
