@echo off
title ZAP ENGINE
color 0A
cls

tasklist /FI "IMAGENAME eq ZAP_ENGINE.exe" 2>NUL | find /I "ZAP_ENGINE.exe" >NUL
if not errorlevel 1 (
    echo  Encerrando instancias antigas do executavel...
    taskkill /F /IM ZAP_ENGINE.exe >NUL 2>&1
    timeout /t 2 /nobreak >nul
)

echo.
echo  ========================================
echo    ZAP ENGINE — Iniciando sistema...
echo  ========================================
echo.

:: ── 1. Docker Desktop ──
echo  [1/5] Verificando Docker...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo  Docker nao estava rodando. Iniciando...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo  Aguardando Docker inicializar...
    :WAIT_DOCKER
    timeout /t 5 /nobreak >nul
    docker info >nul 2>&1
    if %errorlevel% neq 0 goto WAIT_DOCKER
    echo  Docker pronto!
) else (
    echo  Docker ja esta rodando!
)

:: ── 2. Containers ──
echo.
echo  [2/5] Subindo containers...
cd /d "%~dp0"
docker compose up -d
echo  Containers iniciados!

:: ── 3. Aguarda API ──
echo.
echo  [3/5] Aguardando Evolution API (15 segundos)...
timeout /t 15 /nobreak >nul

:: ── 4. Painel Python em nova janela visivel ──
echo.
echo  [4/5] Iniciando painel ZAP Engine...
if not exist logs mkdir logs
set "PY_CMD="
if exist "venv\Scripts\python.exe" set "PY_CMD=venv\Scripts\python.exe"
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
    echo  Python nao encontrado. Instale Python 3 e tente novamente.
    pause
    exit /b 1
)
start "ZAP ENGINE - Painel" /D "%~dp0" cmd /k "%PY_CMD% panel/server.py"

:: Aguarda o painel subir de verdade
echo  Aguardando painel iniciar...
:WAIT_PANEL
timeout /t 3 /nobreak >nul
curl -s http://localhost:5000 >nul 2>&1
if %errorlevel% neq 0 goto WAIT_PANEL
echo  Painel pronto!

:: ── 5. Navegador ──
echo.
echo  [5/5] Abrindo painel no navegador...
start "" http://localhost:5000
timeout /t 3 /nobreak >nul

:: ── 6. Verifica WhatsApp ──
echo.
echo  Verificando WhatsApp...
for /f %%i in ('curl -s "http://localhost:8080/instance/fetchInstances" -H "apikey: evolution-key-2024" 2^>nul ^| find /c "open"') do set CONNECTED=%%i

if "%CONNECTED%"=="1" (
    echo.
    echo  ========================================
    echo    WhatsApp CONECTADO!
    echo    Painel: http://localhost:5000
    echo  ========================================
) else (
    echo.
    echo  WhatsApp desconectado. Gerando QR Code...
    timeout /t 3 /nobreak >nul
    curl -s -X DELETE "http://localhost:8080/instance/delete/meu-whatsapp" -H "apikey: evolution-key-2024" >nul 2>&1
    timeout /t 2 /nobreak >nul
    curl -s -X POST "http://localhost:8080/instance/create" -H "apikey: evolution-key-2024" -H "Content-Type: application/json" -d "{\"instanceName\": \"meu-whatsapp\", \"qrcode\": true, \"integration\": \"WHATSAPP-BAILEYS\"}" >nul 2>&1
    timeout /t 8 /nobreak >nul
    powershell -Command "$r = Invoke-RestMethod -Method GET -Uri 'http://localhost:8080/instance/connect/meu-whatsapp' -Headers @{ 'apikey' = 'evolution-key-2024' }; $b64 = $r.base64; if ($b64) { $html = '<!DOCTYPE html><html><body style=\"display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;background:#080c0a;color:#fff;font-family:sans-serif\"><h2 style=\"color:#25d366\">Escaneie com o WhatsApp</h2><p style=\"color:#6b8c74\">Menu > Dispositivos conectados > Conectar dispositivo</p><img src=\"' + $b64 + '\" style=\"width:280px;background:white;padding:16px;border-radius:12px\"/></body></html>'; $html | Out-File -FilePath \"%~dp0qrcode.html\" -Encoding UTF8; Start-Process \"%~dp0qrcode.html\" }"
    echo  QR Code aberto! Escaneie e acesse: http://localhost:5000
)

echo.
echo  Pressione qualquer tecla para fechar...
pause >nul
