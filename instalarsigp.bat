@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Iniciar SIGp.ps1" -AbrirN8n
if errorlevel 1 (
    echo.
    echo A instalacao ou inicializacao do SIGp falhou. Leia a mensagem acima e pressione uma tecla para fechar.
    pause >nul
)
endlocal
