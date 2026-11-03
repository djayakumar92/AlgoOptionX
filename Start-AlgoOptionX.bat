@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\launch-algooptionx.ps1"
if errorlevel 1 pause
