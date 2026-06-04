@echo off
title DesktopClaw
cd /d "%~dp0frontend"
echo Starting DesktopClaw...
npm run electron:dev
