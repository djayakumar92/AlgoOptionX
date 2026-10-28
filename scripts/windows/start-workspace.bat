@echo off
cd /d "%~dp0..\.."
if not exist .venv\Scripts\algooptionx.exe (
  echo Run uv sync --frozen --extra dev and build the frontend first.
  pause
  exit /b 1
)
.venv\Scripts\algooptionx.exe
