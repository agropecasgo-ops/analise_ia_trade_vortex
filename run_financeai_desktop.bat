@echo off
setlocal
chcp 65001 >nul
title FinanceAI - Iniciar Sistema

set "PROJECT_DIR=d:\Documentos\Analise Inteligente\PROGETO IA"
set "APP_URL=http://127.0.0.1:5000"
set "SERVER_BAT=%PROJECT_DIR%\financeai_server_only.bat"

cd /d "%PROJECT_DIR%" || (
    echo Nao foi possivel acessar a pasta do projeto:
    echo %PROJECT_DIR%
    pause
    exit /b 1
)

echo.
echo ==========================================
echo  FinanceAI - Iniciando sistema
echo ==========================================
echo.

where git >nul 2>nul
if %errorlevel%==0 (
    if exist ".git" (
        echo Verificando atualizacoes do sistema...
        git pull --ff-only
        if errorlevel 1 (
            echo.
            echo Nao foi possivel aplicar atualizacoes automaticamente.
            echo O sistema vai iniciar com os arquivos atuais.
            echo.
        )
    )
)

if exist "requirements.txt" (
    echo.
    echo Conferindo dependencias...
    if exist "venv\Scripts\python.exe" (
        "venv\Scripts\python.exe" -m pip install -r requirements.txt
    ) else (
        python -m pip install -r requirements.txt
    )
)

echo.
echo Verificando se o servidor ja esta ligado...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -UseBasicParsing '%APP_URL%' -TimeoutSec 2; if ($r.StatusCode -ge 200) { exit 0 } else { exit 1 } } catch { exit 1 }"

if errorlevel 1 (
    echo Servidor nao estava ligado. Iniciando agora...
    start "FinanceAI - Servidor" cmd /k ""%SERVER_BAT%""
) else (
    echo Servidor ja esta ligado.
)

echo Aguardando o servidor ficar pronto...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$url='%APP_URL%'; $ok=$false; for ($i=0; $i -lt 60; $i++) { try { $r=Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 2; if ($r.StatusCode -ge 200) { $ok=$true; break } } catch {}; Start-Sleep -Seconds 1 }; if (-not $ok) { exit 1 }"

if errorlevel 1 (
    echo.
    echo O servidor demorou para responder.
    echo Verifique a janela "FinanceAI - Servidor" para detalhes.
    pause
    exit /b 1
)

echo Abrindo sistema em %APP_URL% ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process '%APP_URL%'"

echo.
echo Sistema aberto. A janela do servidor deve permanecer ligada.
echo Se o navegador nao abrir, acesse manualmente: %APP_URL%
exit /b 0
