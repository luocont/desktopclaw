@echo off
title DesktopClaw Launcher
cd /d "%~dp0"

echo ============================================
echo       DesktopClaw Launcher
echo ============================================
echo.

:: ============================================================
:: 1. Check and install Node.js
:: ============================================================
echo [1/4] Checking Node.js...
where node >nul 2>&1
if %errorlevel%==0 (
    for /f "tokens=*" %%i in ('node -v') do echo        Node.js: %%i
    goto :node_done
)

echo        Node.js not found, installing...
echo        Downloading Node.js LTS...

set "NODE_INSTALLER=%TEMP%\node-installer.msi"
powershell -Command "Invoke-WebRequest -Uri 'https://nodejs.org/dist/v22.16.0/node-v22.16.0-x64.msi' -OutFile '%NODE_INSTALLER%'" 2>nul

if not exist "%NODE_INSTALLER%" (
    echo        [ERROR] Failed to download Node.js!
    echo        Please install manually: https://nodejs.org/
    pause
    exit /b 1
)

echo        Installing Node.js (silent)...
msiexec /i "%NODE_INSTALLER%" /quiet /norestart 2>nul
if %errorlevel%==0 (
    echo        Node.js installed successfully!
) else (
    echo        [ERROR] Node.js installation failed!
    echo        Please install manually: https://nodejs.org/
    del "%NODE_INSTALLER%" 2>nul
    pause
    exit /b 1
)
del "%NODE_INSTALLER%" 2>nul

:: Refresh PATH after install
set "PATH=%ProgramFiles%\nodejs;%PATH%"

:node_done

:: ============================================================
:: 2. Check and install Python
:: ============================================================
echo [2/4] Checking Python...
where python >nul 2>&1
if %errorlevel%==0 (
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo        %%i
    goto :python_done
)

echo        Python not found, installing...
echo        Downloading Python 3.12...

set "PYTHON_INSTALLER=%TEMP%\python-installer.exe"
powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile '%PYTHON_INSTALLER%'" 2>nul

if not exist "%PYTHON_INSTALLER%" (
    echo        [ERROR] Failed to download Python!
    echo        Please install manually: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo        Installing Python (silent)...
"%PYTHON_INSTALLER%" /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1 2>nul
if %errorlevel%==0 (
    echo        Python installed successfully!
) else (
    echo        [ERROR] Python installation failed!
    echo        Please install manually: https://www.python.org/downloads/
    del "%PYTHON_INSTALLER%" 2>nul
    pause
    exit /b 1
)
del "%PYTHON_INSTALLER%" 2>nul

:: Refresh PATH after install
set "PATH=%LocalAppData%\Programs\Python\Python312;%LocalAppData%\Programs\Python\Python312\Scripts;%ProgramFiles%\Python312;%ProgramFiles%\Python312\Scripts;%PATH%"

:python_done

:: ============================================================
:: 3. Install frontend dependencies
:: ============================================================
echo [3/4] Checking frontend dependencies...
if not exist "%~dp0frontend\node_modules" (
    echo        Installing frontend dependencies...
    cd /d "%~dp0frontend"
    call npm install
    if %errorlevel% neq 0 (
        echo        [ERROR] npm install failed!
        pause
        exit /b 1
    )
    echo        Frontend dependencies installed!
) else (
    echo        Frontend dependencies OK
)

:: ============================================================
:: 4. Install backend dependencies
:: ============================================================
echo [4/4] Checking backend dependencies...
cd /d "%~dp0backend"
python -c "import desktopclaw" >nul 2>&1
if %errorlevel% neq 0 (
    echo        Installing backend dependencies...
    python -m pip install -e . 2>nul
    if %errorlevel% neq 0 (
        echo        [WARN] pip install failed, trying with --user...
        python -m pip install -e . --user 2>nul
    )
)
echo        Backend dependencies OK

:: ============================================================
:: Start DesktopClaw
:: ============================================================
echo.
echo ============================================
echo   Starting DesktopClaw...
echo ============================================
echo.
cd /d "%~dp0frontend"
call npm run electron:dev

pause
