@echo off
setlocal
cd /d "%~dp0"

echo.
echo  ========================================
echo    ZAP ENGINE - Iniciando sistema
echo  ========================================
echo.

tasklist /FI "IMAGENAME eq ZAP_ENGINE.exe" 2>NUL | find /I "ZAP_ENGINE.exe" >NUL
if not errorlevel 1 (
    echo Encerrando instancias antigas do executavel...
    taskkill /F /IM ZAP_ENGINE.exe >NUL 2>&1
    timeout /t 2 /nobreak >NUL
)

set "PY_CMD="

if exist "venv\Scripts\python.exe" (
    set "PY_CMD=venv\Scripts\python.exe"
)

if not defined PY_CMD (
    for /f "delims=" %%P in ('where py 2^>NUL') do (
        echo %%P | find /I "WindowsApps" >NUL
        if errorlevel 1 if not defined PY_CMD set "PY_CMD=py -3"
    )
)

if not defined PY_CMD (
    for /f "delims=" %%P in ('where python 2^>NUL') do (
        echo %%P | find /I "WindowsApps" >NUL
        if errorlevel 1 if not defined PY_CMD set "PY_CMD=python"
    )
)

if not defined PY_CMD (
    echo.
    echo Python nao encontrado. Instale Python 3 e tente novamente.
    pause
    exit /b 1
)

echo Iniciando pela fonte atualizada...
if /I "%PY_CMD%"=="py -3" (
    py -3 launcher.py
) else (
    %PY_CMD% launcher.py
)
