@echo off
chcp 65001 >nul 2>&1
title Download Python 3.12

set "PY_VERSION=3.12.10"
set "PY_INSTALLER=%TEMP%\python-%PY_VERSION%-amd64.exe"
set "PY_URL=https://www.python.org/ftp/python/%PY_VERSION%/python-%PY_VERSION%-amd64.exe"

echo ============================================
echo   Python %PY_VERSION% Downloader
echo ============================================
echo.

echo [1/2] Downloading Python %PY_VERSION% ...
powershell -Command "Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%PY_INSTALLER%'"

if not exist "%PY_INSTALLER%" (
    echo [ERROR] Download failed!
    pause
    exit /b 1
)

echo [2/2] Launching installer ...
echo TIP: Remember to check "Add Python to PATH" during installation!
start "" "%PY_INSTALLER%"

echo.
echo Done! The installer has been launched.
pause
