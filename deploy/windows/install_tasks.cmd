@echo off
setlocal

REM --- EDIT THESE ---
set APP_DIR=C:\businesaios
set PYTHON_EXE=python

REM Create task: Evolution Worker (on logon)

schtasks /Create /F ^
 /TN "businesaios Evolution Worker" ^
 /SC ONLOGON ^
 /RL HIGHEST ^
 /TR "cmd /c cd /d %APP_DIR% && set RUN_MODE=evolution && %PYTHON_EXE% main.py"

REM Create task: Telegram Runtime (on logon)

schtasks /Create /F ^
 /TN "businesaios Telegram Runtime" ^
 /SC ONLOGON ^
 /RL HIGHEST ^
 /TR "cmd /c cd /d %APP_DIR% && set RUN_MODE=telegram && %PYTHON_EXE% main.py"

echo Installed tasks.

endlocal
