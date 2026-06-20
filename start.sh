#!/bin/bash
# lucas-task-life — Script de inicialização (Microserviços)
# Execute com: ./start.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT=9999

echo ""
echo "  ██╗     ██╗   ██╗ ██████╗ █████╗ ███████╗     ██████╗ ███████╗"
echo "  ██║     ██║   ██║██╔════╝██╔══██╗██╔════╝    ██╔═══██╗██╔════╝"
echo "  ██║     ██║   ██║██║     ███████║███████╗    ██║   ██║███████╗"
echo "  ██║     ██║   ██║██║     ██╔══██║╚════██║    ██║   ██║╚════██║"
echo "  ███████╗╚██████╔╝╚██████╗██║  ██║███████║    ╚██████╔╝███████║"
echo "  ╚══════╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝╚══════╝     ╚═════╝ ╚══════╝"
echo ""
echo "  SRE Dashboard (Microservices Edition) — v3.0"
echo "  ───────────────────────────────────────────"

# Verifica se o Docker está rodando
if ! docker info >/dev/null 2>&1; then
    echo "  [ERRO] O Docker daemon não está rodando. Por favor, inicie o Docker e tente novamente."
    exit 1
fi

# Verifica se o .env existe
if [ ! -f ".env" ]; then
    echo "  [INFO] Arquivo .env não encontrado. Criando com valores padrão..."
    echo "OBSIDIAN_VAULT_PATH=/home/elvenworks24/lucas-notes" > .env
fi

# Derruba containers antigos
echo "  [INFO] Limpando containers anteriores..."
docker compose down -v 2>/dev/null

echo "  [INFO] Iniciando microserviços..."
docker compose up --build -d

echo ""
echo "  [INFO] Status dos containers:"
docker compose ps

echo ""
echo "  [INFO] Servidor rodando em http://127.0.0.1:$PORT"
echo "  [INFO] Logs do API Gateway (Nginx):"
echo "  ───────────────────────────────────────────"
echo ""

# Abre o browser automaticamente após 1.5s
(sleep 1.5 && xdg-open "http://127.0.0.1:$PORT" 2>/dev/null || true) &

# Mostra logs do gateway
docker compose logs -f gateway
