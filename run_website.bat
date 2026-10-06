@echo off
title MIGRIGA Luxury Beauty Store & Backend Server
cd /d "%~dp0"
echo =========================================================
echo   MIGRIGA Haute Beaute - Full-Stack E-Commerce Server
echo   FastAPI + SQLite Database + Admin Portal
echo =========================================================
echo.
echo Starting server on http://127.0.0.1:3000 ...
start "" "http://127.0.0.1:3000"
python server.py
pause
