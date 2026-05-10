@echo off
title Rental Agent
cd /d "%~dp0"

echo ================================
echo  Rental Agent — Starting up
echo ================================
echo.
echo [1/2] Starting Telegram bot (Yad2 on-demand)...
start "Rental Bot" cmd /k "python src\bot_listener.py"

timeout /t 2 /nobreak >nul

echo [2/2] Starting scheduler (Facebook auto-scan)...
start "Rental Scheduler" cmd /k "python src\scheduler.py"

echo.
echo Both processes are running in separate windows.
echo Close those windows to stop the agent.
pause
