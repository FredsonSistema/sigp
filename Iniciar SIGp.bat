@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Iniciar SIGp.ps1"
if errorlevel 1 (
    echo.
    echo O SIGp nao iniciou. Leia a mensagem acima e pressione uma tecla para fechar.
    pause >nul
)
endlocal
