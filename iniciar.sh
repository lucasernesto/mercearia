#!/usr/bin/env sh
# Prepara o ambiente (na primeira vez) e inicia a mercearia. Linux e macOS.
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  PY=$(command -v python3 || command -v python || true)
  if [ -z "$PY" ] || ! "$PY" -c 'import sys; sys.exit(sys.version_info < (3, 9))'; then
    echo "Python 3.9 ou mais recente não encontrado." >&2
    exit 1
  fi
  echo "Criando ambiente virtual (.venv)..."
  if ! "$PY" -m venv .venv; then
    rm -rf .venv
    echo "Falha ao criar o .venv. No Debian/Ubuntu instale antes: sudo apt install python3-venv" >&2
    exit 1
  fi
fi

if [ -x .venv/bin/python ]; then VPY=.venv/bin/python; else VPY=.venv/Scripts/python.exe; fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Arquivo .env criado a partir do .env.example. Edite-o para trocar a senha do painel."
fi

echo "Instalando dependências..."
"$VPY" -m pip install -q --disable-pip-version-check -r requirements.txt
exec "$VPY" app.py
