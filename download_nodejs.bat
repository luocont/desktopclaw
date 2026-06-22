@echo off
chcp 65001 >nul 2>&1
title Download Node.js

set "NODE_VERSION=22.16.0"
set "NODE_INSTALLER=%TEMP%\node-v%NODE_VERSION%-x64.msi"
set "NODE_URL=https://nodejs.org/dist/v%NODE_VERSION%/node-v%NODE_VERSION%-x64.msi"

echo ============================================
echo   Node.js v%NODE_VERSION% Downloader
echo ============================================
echo.

echo [1/2] Downloading Node.js v%NODE_VERSION% ...
powershell -Command "Invoke-WebRequest -Uri '%NODE_URL%' -OutFile '%NODE_INSTALLER%'"

if not exist "%NODE_INSTALLER%" (
    echo [ERROR] Download failed!
    pause
    exit /b 1
)

echo [2/2] Launching installer ...
start "" "%NODE_INSTALLER%"

echo.
echo Done! The installer has been launched.
pause
