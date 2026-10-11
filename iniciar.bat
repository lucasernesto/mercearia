@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" goto instalar

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY goto sem_python

%PY% -c "import sys; sys.exit(sys.version_info < (3, 9))" || goto sem_python
echo Criando ambiente virtual (.venv)...
%PY% -m venv .venv || goto falhou

:instalar
if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo Arquivo .env criado a partir do .env.example. Edite-o para trocar a senha do painel.
)
echo Instalando dependencias...
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt || goto falhou

".venv\Scripts\python.exe" app.py
goto fim

:sem_python
echo Python 3.9 ou mais recente nao encontrado.
echo Instale em https://www.python.org/downloads/ marcando "Add python.exe to PATH".
goto falhou

:falhou
echo.
echo Nao foi possivel iniciar a mercearia.
pause
exit /b 1

:fim
endlocal
