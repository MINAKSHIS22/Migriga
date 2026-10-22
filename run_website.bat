@echo off
title MIGRIGA British Heritage Living & Backend Server
cd /d "%~dp0"
echo =========================================================
echo   MIGRIGA British Heritage Living - Full-Stack E-Commerce Server
echo   FastAPI + SQLite Database + Admin Portal
echo =========================================================
echo.
echo Starting server on http://127.0.0.1:3000/welcome.html ...
start "" "http://127.0.0.1:3000/welcome.html"
python server.py
pause
