@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Parar SIGp.ps1"
if errorlevel 1 (
    echo.
    echo Ocorreu um erro ao parar os servicos. Pressione uma tecla para fechar.
    pause >nul
)
endlocal
