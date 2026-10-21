@echo off
setlocal
cd /d "%~dp0"
title Sistema de Pedidos e Estoque

where py >nul 2>nul
if %errorlevel%==0 (set PY=py -3) else (set PY=python)

if not exist ".env" copy ".env.example" ".env" >nul

if not exist ".venv\Scripts\python.exe" (
  echo Criando ambiente virtual...
  %PY% -m venv .venv || goto erro
)

echo Instalando dependencias...
".venv\Scripts\python.exe" -m pip install -q --upgrade pip
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || goto erro

if not exist "dados\estoque.db" (
  echo Gerando dados ficticios de demonstracao...
  ".venv\Scripts\python.exe" -m scripts.popular_banco || goto erro
)

echo.
echo Painel: http://127.0.0.1:8000   (feche esta janela para parar)
start "" http://127.0.0.1:8000
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-server-header --no-access-log
goto fim

:erro
echo.
echo Algo falhou. Veja a mensagem acima.
pause
:fim
endlocal
