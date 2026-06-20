# Lucas_OS — SRE Dashboard (Microservices)

Dashboard pessoal gamificado para SRE Engineer, integrado ao Obsidian vault, iCal Calendars e metas de carreira, rodando em uma arquitetura moderna de microserviços dockerizados.

Inspirado no **RETRO_OS** do Tuca, adaptado para o contexto de um SRE com foco em produtividade, hábitos, estudo e carreira.

---

## 🎨 Desenho da Arquitetura

O sistema é decomposto em **4 microserviços** isolados rodando via Docker Compose:

- **`gateway` (Nginx)**: Escuta na porta `9999`. Serve a Single Page Application (HTML/CSS/JS) e atua como API Gateway, roteando requisições `/api/*` para os microserviços adequados.
- **`vault-service` (FastAPI - :9001)**: Responsável por processar arquivos Markdown no Obsidian Vault (tarefas, hábitos, notas diárias, manifesto, study plan).
- **`calendar-service` (FastAPI - :9002)**: Realiza integração, parse e cache dos calendários externos (Google Calendar e Outlook).
- **`gamification-service` (FastAPI - :9003)**: Gerencia o sistema de XP, levels, ranks, conquistas, metas financeiras e configurações gerais (`config.json`).

---

## ✨ Features por Aba

| Aba | O que faz | Serviço Responsável |
|---|---|---|
| **HOME** | Identidade, XP/Level, Streak, Manifesto, Status dos sistemas | `gamification-service` + `vault-service` |
| **ESTUDOS** | Progresso real do Study Plan 30-60-90 days | `vault-service` |
| **PROJETOS** | Board de projetos + Quest Board com toggle done/undone | `vault-service` |
| **ROTINA** | Grade semanal de hábitos via notas diárias Obsidian | `vault-service` |
| **AGENDA** | Timeline de eventos Google Calendar + Outlook (iCal) | `calendar-service` |
| **STATS** | Gráficos de XP e consistência de hábitos | `gamification-service` + `vault-service` |
| **FINANCEIRO**| Metas financeiras e de carreira SRE | `gamification-service` |

---

## 🛠️ Stack Tecnológica

- **Orquestração**: Docker Compose
- **Proxy/Gateway**: Nginx
- **Backend Services**: Python 3.10 + FastAPI + Uvicorn
- **Frontend SPA**: HTML + CSS + JavaScript puros (sem dependências como Node/npm)
- **Design System**: Paleta azul elétrico, scan lines CRT, fontes Space Grotesk + JetBrains Mono.

---

## 🚀 Como Executar

Certifique-se de possuir o **Docker** e **Docker Compose** instalados em sua máquina.

```bash
git clone https://github.com/lumr92/lucas-task-life.git
cd lucas-task-life

# 1. Copie o template de configuração e crie a config local
cp config.example.json config.json

# 2. Crie o arquivo .env com o caminho do seu Obsidian Vault no Host
echo "OBSIDIAN_VAULT_PATH=/home/elvenworks24/lucas-notes" > .env

# 3. Inicialize os microserviços (irá buildar as imagens na primeira execução)
./start.sh
```

Acesse a aplicação no navegador em: **http://127.0.0.1:9999**

Para parar a aplicação, você pode pressionar `Ctrl+C` no terminal que acompanha os logs ou rodar `docker compose down`.

---

## 📁 Estrutura de Diretórios

```
lucas-task-life/
├── docker-compose.yml     # Orquestrador dos microserviços
├── .env                  # Variáveis de ambiente locais (ignorado no Git)
├── config.json           # Configuração central (ignorado no Git)
├── config.example.json   # Template de configuração
├── start.sh              # Script de inicialização automática SRE
│
├── gateway/
│   └── nginx.conf        # Configuração de rotas e proxy reverso do Nginx
│
├── services/
│   ├── vault-service/    # Parser do Obsidian vault
│   ├── calendar-service/ # Parser de iCal Google/Outlook
│   └── gamification-service/ # Gerenciador de XP, níveis e config
│
├── templates/
│   └── index.html        # SPA frontend (HTML)
└── static/
    ├── style.css         # Design system e estilizações
    └── app.js            # Lógica cliente e gráficos Canvas
```
