@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Smart Lecture Rooms - Installer
cd /d "%~dp0"

echo ===========================================================================
echo  Smart Lecture Room Notification System v3.0 - Windows installer
echo ===========================================================================
echo.
echo  This will:
echo    1. Check for Python 3.11 or newer.
echo    2. Create backend\.venv and install the Python packages.
echo    3. Create backend\.env with a random SECRET_KEY.
echo    4. Create the SQLite database and demo accounts.
echo    5. Build the web front end only when Node.js is available.
echo.
echo  The installer is safe to run again. Existing data and .env are kept.
echo.

rem ---------------------------------------------------------------- Python ---
set "PYTHON="
where py >nul 2>nul
if errorlevel 1 goto :try_python
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 goto :try_python
set "PYTHON=py -3"
goto :python_ready

:try_python
where python >nul 2>nul
if errorlevel 1 goto :no_python
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 goto :no_python
set "PYTHON=python"

:python_ready
echo [1/5] Python found: %PYTHON%
%PYTHON% --version

rem ----------------------------------------------------------------- venv ---
set "VENV=%~dp0backend\.venv"
set "VENV_PY=%VENV%\Scripts\python.exe"
if exist "%VENV_PY%" goto :venv_ready

echo [2/5] Creating the virtual environment...
%PYTHON% -m venv "%VENV%"
if errorlevel 1 goto :fail
goto :venv_installed

:venv_ready
echo [2/5] Virtual environment already exists.

:venv_installed
if not exist "%VENV_PY%" (
    echo ERROR: The virtual environment was not created correctly.
    goto :fail
)

echo [3/5] Installing Python packages...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 goto :fail
"%VENV_PY%" -m pip install -r "%~dp0backend\requirements.txt"
if errorlevel 1 goto :fail

rem ------------------------------------------------------------------ .env ---
if exist "%~dp0backend\.env" goto :env_ready
echo [4/5] Creating backend\.env with a random secret key...
copy /y "%~dp0backend\.env.example" "%~dp0backend\.env" >nul
if errorlevel 1 goto :fail
"%VENV_PY%" -c "from pathlib import Path; import re, secrets; p = Path(r'%~dp0backend\.env'); text = p.read_text(encoding='utf-8'); text = re.sub(r'(?m)^SECRET_KEY=.*$', 'SECRET_KEY=' + secrets.token_urlsafe(48), text); p.write_text(text, encoding='utf-8')"
if errorlevel 1 goto :fail
goto :env_done

:env_ready
echo [4/5] Keeping the existing backend\.env.

:env_done
rem ------------------------------------------------------------- database ---
echo [5/5] Creating the database and demo data...
pushd "%~dp0backend"
"%VENV_PY%" manage.py init-db
if errorlevel 1 goto :fail_pop
"%VENV_PY%" manage.py seed
if errorlevel 1 goto :fail_pop
popd

rem --------------------------------------------------------------- front end ---
if exist "%~dp0backend\app\static\index.html" goto :static_ready
echo.
echo Front-end build not found. Trying Node.js...
where npm >nul 2>nul
if errorlevel 1 (
    echo ERROR: The prebuilt front end is missing and npm is not installed.
    echo Install Node.js 20+ and run this installer again.
    goto :fail
)
pushd "%~dp0frontend"
call npm ci
if errorlevel 1 goto :fail_pop
call npm run build
if errorlevel 1 goto :fail_pop
popd

:static_ready
echo.
echo ===========================================================================
echo  Installation complete.
echo ===========================================================================
echo.
echo  Start the system by double-clicking:  start.bat
echo  Then open:                            http://127.0.0.1:5000
echo.
echo  Demo accounts (change them before real use):
echo    Administrator  admin   / Admin@123
echo    Officer        otieno  / Officer@123
echo.
echo  To change a password:
echo    backend\.venv\Scripts\python.exe backend\manage.py reset-password admin
echo.
pause
exit /b 0

:no_python
echo.
echo ERROR: Python 3.11 or newer was not found.
echo Install it from https://www.python.org/downloads/ and tick
echo "Add python.exe to PATH", then run this installer again.
goto :fail

:fail_pop
popd

:fail
echo.
echo Installation stopped because of the error above.
pause
exit /b 1
