#!/bin/bash
# Lucas_OS — Script de inicialização
# Execute com: ./start.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"
PORT=9999

echo ""
echo "  ██╗     ██╗   ██╗ ██████╗ █████╗ ███████╗     ██████╗ ███████╗"
echo "  ██║     ██║   ██║██╔════╝██╔══██╗██╔════╝    ██╔═══██╗██╔════╝"
echo "  ██║     ██║   ██║██║     ███████║███████╗    ██║   ██║███████╗"
echo "  ██║     ██║   ██║██║     ██╔══██║╚════██║    ██║   ██║╚════██║"
echo "  ███████╗╚██████╔╝╚██████╗██║  ██║███████║    ╚██████╔╝███████║"
echo "  ╚══════╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝╚══════╝     ╚═════╝ ╚══════╝"
echo ""
echo "  SRE Dashboard — v2.0"
echo "  ─────────────────────────────────────"

# Verifica se o venv existe
if [ ! -d "$VENV" ]; then
    echo "  [SETUP] Criando ambiente virtual..."
    python3 -m venv "$VENV"
    echo "  [SETUP] Instalando dependências..."
    "$VENV/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" -q
    echo "  [SETUP] Pronto!"
fi

# Mata processo anterior na porta se existir
if lsof -Pi :$PORT -sTCP:LISTEN -t &>/dev/null; then
    echo "  [INFO]  Porta $PORT em uso — encerrando processo anterior..."
    fuser -k ${PORT}/tcp 2>/dev/null
    sleep 1
fi

echo "  [INFO]  Iniciando servidor em http://127.0.0.1:$PORT"
echo "  [INFO]  Pressione Ctrl+C para parar"
echo "  ─────────────────────────────────────"
echo ""

# Abre o browser automaticamente após 1.5s (em background)
(sleep 1.5 && xdg-open "http://127.0.0.1:$PORT" 2>/dev/null || true) &

# Inicia o servidor
cd "$SCRIPT_DIR"
"$VENV/bin/uvicorn" main:app --host 127.0.0.1 --port $PORT
