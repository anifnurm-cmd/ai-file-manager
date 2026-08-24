@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo ================================================
echo AI FILE MANAGER - ONE CLICK SETUP
echo ================================================
echo Chat model:      qwen3-vl:8b
echo Embedding model: qwen3-embedding:0.6b
echo.
echo First setup downloads several GB of models.
echo.

where winget >nul 2>&1 || (echo ERROR: WinGet is required.&pause&exit /b 1)
where py >nul 2>&1 || (echo Installing Python 3.13...&winget install --id Python.Python.3.13 -e --silent --accept-source-agreements --accept-package-agreements&if errorlevel 1 (echo ERROR: Python install failed.&pause&exit /b 1))
py -3.13 --version >nul 2>&1 || (echo ERROR: Python 3.13 unavailable. Open a new Command Prompt and retry.&pause&exit /b 1)

set "OLLAMA_EXE="
for /f "delims=" %%O in ('where ollama 2^>nul') do if not defined OLLAMA_EXE set "OLLAMA_EXE=%%O"
if not defined OLLAMA_EXE if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if not defined OLLAMA_EXE if exist "%ProgramFiles%\Ollama\ollama.exe" set "OLLAMA_EXE=%ProgramFiles%\Ollama\ollama.exe"
if not defined OLLAMA_EXE (
  echo Installing Ollama...
  winget install --id Ollama.Ollama -e --silent --accept-source-agreements --accept-package-agreements
  if errorlevel 1 powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://ollama.com/install.ps1 ^| iex"
)
set "OLLAMA_EXE="
for /f "delims=" %%O in ('where ollama 2^>nul') do if not defined OLLAMA_EXE set "OLLAMA_EXE=%%O"
if not defined OLLAMA_EXE if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if not defined OLLAMA_EXE if exist "%ProgramFiles%\Ollama\ollama.exe" set "OLLAMA_EXE=%ProgramFiles%\Ollama\ollama.exe"
if not defined OLLAMA_EXE (echo ERROR: Ollama executable not found.&pause&exit /b 1)

winget upgrade --id Ollama.Ollama -e --silent --accept-source-agreements --accept-package-agreements >nul 2>&1

curl.exe -s http://127.0.0.1:11434/api/version >nul 2>&1 || start "Ollama" /min "%OLLAMA_EXE%" serve
set /a WAIT=0
:WAIT_OLLAMA
curl.exe -s http://127.0.0.1:11434/api/version >nul 2>&1 && goto OLLAMA_READY
set /a WAIT+=1
if !WAIT! GEQ 90 (echo ERROR: Ollama API did not start.&pause&exit /b 1)
timeout /t 1 /nobreak >nul
goto WAIT_OLLAMA
:OLLAMA_READY

set "CHAT_MODEL=qwen3-vl:8b"
set "EMBED_MODEL=qwen3-embedding:0.6b"
"%OLLAMA_EXE%" list | findstr /i /c:"%CHAT_MODEL%" >nul 2>&1 || "%OLLAMA_EXE%" pull "%CHAT_MODEL%"
if errorlevel 1 (echo ERROR: Failed to download %CHAT_MODEL%.&pause&exit /b 1)
"%OLLAMA_EXE%" list | findstr /i /c:"%EMBED_MODEL%" >nul 2>&1 || "%OLLAMA_EXE%" pull "%EMBED_MODEL%"
if errorlevel 1 (echo ERROR: Failed to download %EMBED_MODEL%.&pause&exit /b 1)

if not exist ".venv\Scripts\python.exe" py -3.13 -m venv .venv
if errorlevel 1 (echo ERROR: Failed to create Python environment.&pause&exit /b 1)
.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (echo ERROR: pip bootstrap failed.&pause&exit /b 1)
.venv\Scripts\python.exe -m pip install --prefer-binary -r requirements.txt
if errorlevel 1 (echo ERROR: Python dependencies failed.&pause&exit /b 1)
.venv\Scripts\python.exe -m pip check
if errorlevel 1 (echo ERROR: dependency conflict detected.&pause&exit /b 1)
.venv\Scripts\python.exe -m py_compile runner.py legacy_app.py
if errorlevel 1 (echo ERROR: Python compilation failed.&pause&exit /b 1)

set "OLLAMA_URL=http://127.0.0.1:11434"
set "OLLAMA_CHAT_MODEL=%CHAT_MODEL%"
set "OLLAMA_EMBED_MODEL=%EMBED_MODEL%"
set "PORT=8787"

echo.
echo ================================================
echo AI FILE MANAGER READY
echo ================================================
echo URL: http://127.0.0.1:8787
echo.
start "AI File Manager Server" cmd /k "cd /d ""%~dp0"" && set OLLAMA_URL=%OLLAMA_URL% && set OLLAMA_CHAT_MODEL=%OLLAMA_CHAT_MODEL% && set OLLAMA_EMBED_MODEL=%OLLAMA_EMBED_MODEL% && set PORT=%PORT% && .venv\Scripts\python.exe runner.py"
timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:8787"
exit /b 0
