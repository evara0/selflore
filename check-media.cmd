@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\check-media.ps1" %*
exit /b %errorlevel%
