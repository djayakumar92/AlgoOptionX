@echo off
cd /d %~dp0
call .venv\Scripts\activate.bat
echo Starting NIFTY Options Analyzer... your browser will open automatically.
echo Keep this window open while you use the dashboard. Close it to stop.
python -m uvicorn dhan_analyzer.api.app:app --host 127.0.0.1 --port 8000
pause
