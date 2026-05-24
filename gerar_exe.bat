@echo off
setlocal
cd /d "%~dp0"

echo.
echo  ========================================
echo    ZAP ENGINE - Gerando executavel
echo  ========================================
echo.

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

echo Atualizando dependencias...
if /I "%PY_CMD%"=="py -3" (
    py -3 -m pip install --upgrade pip
    py -3 -m pip install -r requirements.txt
    py -3 -m pip install pyinstaller
    py -3 -m PyInstaller --clean --noconfirm build.spec
) else (
    %PY_CMD% -m pip install --upgrade pip
    %PY_CMD% -m pip install -r requirements.txt
    %PY_CMD% -m pip install pyinstaller
    %PY_CMD% -m PyInstaller --clean --noconfirm build.spec
)

echo.
echo  Build concluido. Executavel em dist\ZAP_ENGINE.exe
pause
