@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo ================================================
echo          AI FILE MANAGER - ONE CLICK SETUP
echo ================================================
echo.
echo This first run may download several GB of AI models.
echo Keep this window open until the browser opens.
echo.

where winget >nul 2>&1
if errorlevel 1 (
    echo ERROR: WinGet was not found.
    echo Install/update "App Installer" from Microsoft Store, then run this file again.
    pause
    exit /b 1
)

where py >nul 2>&1
if errorlevel 1 (
    echo Python launcher not found. Installing Python 3.13...
    winget install --id Python.Python.3.13 -e --silent --accept-source-agreements --accept-package-agreements
    if errorlevel 1 (
        echo ERROR: Python 3.13 installation failed.
        pause
        exit /b 1
    )
)

where py >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python launcher is still unavailable after installation.
    echo Close this window, open a new Command Prompt, and run start.bat again.
    pause
    exit /b 1
)

py -3.13 --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.13 is not available to the Python launcher.
    py --version
    pause
    exit /b 1
)

echo Python:
py -3.13 --version

set "OLLAMA_EXE="
for /f "delims=" %%O in ('where ollama 2^>nul') do if not defined OLLAMA_EXE set "OLLAMA_EXE=%%O"
if not defined OLLAMA_EXE if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if not defined OLLAMA_EXE if exist "%ProgramFiles%\Ollama\ollama.exe" set "OLLAMA_EXE=%ProgramFiles%\Ollama\ollama.exe"

if not defined OLLAMA_EXE (
    echo Ollama not found. Installing Ollama...
    winget install --id Ollama.Ollama -e --silent --accept-source-agreements --accept-package-agreements
    if errorlevel 1 (
        echo WinGet install failed. Trying Ollama official installer...
        powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://ollama.com/install.ps1 | iex"
        if errorlevel 1 (
            echo ERROR: Ollama installation failed.
            pause
            exit /b 1
        )
    )
)

set "OLLAMA_EXE="
for /f "delims=" %%O in ('where ollama 2^>nul') do if not defined OLLAMA_EXE set "OLLAMA_EXE=%%O"
if not defined OLLAMA_EXE if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if not defined OLLAMA_EXE if exist "%ProgramFiles%\Ollama\ollama.exe" set "OLLAMA_EXE=%ProgramFiles%\Ollama\ollama.exe"
if not defined OLLAMA_EXE (
    echo ERROR: Ollama executable was not found after installation.
    echo Reboot Windows once, then run start.bat again if installation completed.
    pause
    exit /b 1
)

echo Ollama:
"%OLLAMA_EXE%" --version

curl.exe -s http://127.0.0.1:11434/api/version >nul 2>&1
if errorlevel 1 (
    echo Starting Ollama background service...
    start "Ollama" /min "%OLLAMA_EXE%" serve
)

set /a WAIT=0
:WAIT_OLLAMA
curl.exe -s http://127.0.0.1:11434/api/version >nul 2>&1
if not errorlevel 1 goto OLLAMA_READY
set /a WAIT+=1
if !WAIT! GEQ 60 (
    echo ERROR: Ollama API did not become available within 60 seconds.
    echo Try opening Ollama once from the Start menu and run this file again.
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto WAIT_OLLAMA

:OLLAMA_READY
echo Ollama API: READY

set "OLLAMA_CHAT_MODEL=qwen3-vl:8b"
set "OLLAMA_EMBED_MODEL=nomic-embed-text"

echo.
echo Checking AI model: %OLLAMA_CHAT_MODEL%
"%OLLAMA_EXE%" list | findstr /i /c:"%OLLAMA_CHAT_MODEL%" >nul 2>&1
if errorlevel 1 (
    echo Downloading %OLLAMA_CHAT_MODEL% ...
    "%OLLAMA_EXE%" pull %OLLAMA_CHAT_MODEL%
    if errorlevel 1 (
        echo ERROR: Failed to download %OLLAMA_CHAT_MODEL%.
        pause
        exit /b 1
    )
)

echo Checking embedding model: %OLLAMA_EMBED_MODEL%
"%OLLAMA_EXE%" list | findstr /i /c:"%OLLAMA_EMBED_MODEL%" >nul 2>&1
if errorlevel 1 (
    echo Downloading %OLLAMA_EMBED_MODEL% ...
    "%OLLAMA_EXE%" pull %OLLAMA_EMBED_MODEL%
    if errorlevel 1 (
        echo ERROR: Failed to download %OLLAMA_EMBED_MODEL%.
        pause
        exit /b 1
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python virtual environment...
    py -3.13 -m venv .venv
    if errorlevel 1 (
        echo ERROR: Could not create .venv.
        pause
        exit /b 1
    )
)

.venv\Scripts\python.exe --version
.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo ERROR: pip bootstrap failed.
    pause
    exit /b 1
)

.venv\Scripts\python.exe -m pip install --prefer-binary -r requirements.txt
if errorlevel 1 (
    echo ERROR: Python dependency installation failed.
    pause
    exit /b 1
)

.venv\Scripts\python.exe -m pip check
if errorlevel 1 (
    echo ERROR: Python dependency conflict detected.
    pause
    exit /b 1
)

.venv\Scripts\python.exe -m py_compile app.py
if errorlevel 1 (
    echo ERROR: Application compilation failed.
    pause
    exit /b 1
)

set "OLLAMA_URL=http://127.0.0.1:11434"
set "OLLAMA_CHAT_MODEL=qwen3-vl:8b"
set "OLLAMA_EMBED_MODEL=nomic-embed-text"
set "PORT=8787"

echo.
echo ================================================
echo          AI FILE MANAGER IS READY
echo ================================================
echo Chat model:      %OLLAMA_CHAT_MODEL%
echo Embedding model: %OLLAMA_EMBED_MODEL%
echo Web app:         http://127.0.0.1:8787
echo ================================================
echo.

start "AI File Manager Server" cmd /k "cd /d ""%~dp0"" && set OLLAMA_URL=%OLLAMA_URL% && set OLLAMA_CHAT_MODEL=%OLLAMA_CHAT_MODEL% && set OLLAMA_EMBED_MODEL=%OLLAMA_EMBED_MODEL% && set PORT=%PORT% && .venv\Scripts\python.exe app.py"
timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:8787"
exit /b 0
