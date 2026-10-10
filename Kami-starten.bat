@echo off
setlocal
cd /d "%~dp0backend"
if errorlevel 1 (
  echo Backend-Ordner nicht gefunden.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Python-Umgebung backend\.venv nicht gefunden.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" server.py
if errorlevel 1 (
  echo.
  echo Kami konnte nicht erfolgreich ausgefuehrt werden. Fehlermeldung siehe oben.
  pause
)
