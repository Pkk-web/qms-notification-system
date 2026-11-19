@echo off
setlocal EnableExtensions
title Smart Lecture Rooms - Server
cd /d "%~dp0"

set "VENV_PY=%~dp0backend\.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo ===========================================================================
    echo  Smart Lecture Rooms is not installed yet.
    echo ===========================================================================
    echo.
    echo  Run install.bat first, then run this file again.
    echo.
    pause
    exit /b 1
)

if not exist "%~dp0backend\.env" (
    echo Creating backend\.env from the example...
    copy /y "%~dp0backend\.env.example" "%~dp0backend\.env" >nul
)

if not exist "%~dp0backend\app\static\index.html" (
    echo WARNING: the front-end build is missing. Run install.bat before using the app.
    echo.
)

echo ===========================================================================
echo  Smart Lecture Room Notification System v3.0
echo ===========================================================================
echo.
echo  Server:  http://127.0.0.1:5000
echo  Console: http://127.0.0.1:5000/#/console
echo.
echo  Keep this window open while the system is in use.
echo  Press Ctrl+C to stop the server.
echo.

pushd "%~dp0backend"

rem Open the browser a few seconds after the server starts. The console follows
rem the same SQLite database and audio scheduler as the display.
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process 'http://127.0.0.1:5000'"

"%VENV_PY%" run.py
set "EXITCODE=%ERRORLEVEL%"

popd

echo.
if not "%EXITCODE%"=="0" (
    echo The server stopped with exit code %EXITCODE%.
    echo Check the messages above, then run start.bat again.
) else (
    echo The server has stopped.
)
echo.
pause
exit /b %EXITCODE%
