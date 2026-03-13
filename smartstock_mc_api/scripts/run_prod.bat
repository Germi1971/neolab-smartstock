@echo off
cd /d %~dp0\..
set PYTHONUNBUFFERED=1
uvicorn app.main:app --host 0.0.0.0 --port 8010
pause
