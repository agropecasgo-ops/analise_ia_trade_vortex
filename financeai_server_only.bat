@echo off
setlocal
chcp 65001 >nul
title FinanceAI - Servidor

set "PROJECT_DIR=d:\Documentos\Analise Inteligente\PROGETO IA"

cd /d "%PROJECT_DIR%" || (
    echo Nao foi possivel acessar a pasta do projeto:
    echo %PROJECT_DIR%
    pause
    exit /b 1
)

if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
)

echo Servidor FinanceAI iniciando em http://127.0.0.1:5000
echo Para parar o sistema, feche esta janela ou pressione Ctrl+C.
echo.
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" -c "import app as financeai_app; financeai_app.app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)"
) else (
    python -c "import app as financeai_app; financeai_app.app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)"
)

echo.
echo Servidor encerrado.
pause
