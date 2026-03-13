@echo off
cd /d %~dp0\..
set PYTHONUNBUFFERED=1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8010
pause
