# lucas-task-life — Arquivo de Contexto do Agente

Este arquivo foi criado para registrar o estado atual do projeto, sua arquitetura e as decisões técnicas tomadas, facilitando a retomada em sessões futuras por qualquer agente.

---

## 📌 Visão Geral do Projeto
O `lucas-task-life` é um dashboard pessoal e gamificado voltado para a rotina e estudos de um SRE/Platform Engineer (**Lucas**). Ele consolida e gamifica informações do Obsidian Vault local do usuário, lê agendas iCal e acompanha metas de carreira/financeiras.

---

## ⚙️ Arquitetura de Microserviços (v3.0)

O projeto foi migrado de um monolito para uma arquitetura distribuída usando **Docker Compose** e um **Nginx API Gateway**.

```
                           +----------------------+
                           |  Browser (Port 9999) |
                           +----------+-----------+
                                      |
                                      v
                           +----------+-----------+
                           |   Nginx Gateway      |
                           +----+-----+-----+-----+
                                |     |     |
            +-------------------+     |     +-------------------+
            | /                       | /api/calendar           | /api/(habits|quests|...)
            v                         v                         v
  +---------+---------+     +---------+---------+     +---------+---------+
  + Servir HTML/JS/CSS+     | calendar-service  |     |   vault-service   |
  +-------------------+     |     (Port 9002)   |     |    (Port 9001)    |
                            +---------+---------+     +----+---------+----+
                                      |                    |         |
                                      |                    |         | (Leitura/Escrita)
                                      |                    |         v
                                      | (Obter config)     |   +-----+-----+
                                      v                    |   | Obsidian  |
                            +---------+---------+          |   |  Vault    |
                            |gamification-serv. |<---------+   |  (/vault) |
                            |     (Port 9003)   | (Internal    +-----------+
                            |   (Config/XP/LVL) |  vault-data)
                            +-------------------+
```

### Detalhes de Portas e Endpoints (Iniciando com 9)
*   **Porta `9999`:** Nginx Gateway (Porta pública acessada no navegador). Servindo `templates/index.html` na rota `/` e assets estáticos em `/static/`.
*   **Porta `9001`:** `vault-service` (FastAPI). Processa os arquivos markdown do vault do Obsidian.
*   **Porta `9002`:** `calendar-service` (FastAPI). Parseia agendas iCal do Outlook e Google.
*   **Porta `9003`:** `gamification-service` (FastAPI). Gerencia XP, níveis, metas e o `config.json`.

---

## 📁 Estrutura do Workspace

```
lucas-task-life/
├── docker-compose.yml       # Orquestrador dos microserviços Docker
├── .env                    # Declaração do path do Obsidian (Host -> Container)
├── config.json             # Configuração de hábitos, metas e URLs de calendário (Ignorado no Git)
├── config.example.json     # Template padrão de configurações
├── start.sh                # Script de inicialização automática da stack
├── context.md              # Este arquivo de contexto/memória
├── .gitignore              # Ignora .env, config.json, logs, .venv
├── templates/
│   └── index.html          # SPA (Single Page Application) com 7 abas
├── static/
│   ├── style.css           # Design System (Azul Elétrico, CRT scanlines, Space Grotesk)
│   └── app.js              # Roteador frontend e renderizadores de aba
└── services/
    ├── vault-service/      # Código do microserviço do Obsidian
    ├── calendar-service/   # Código do microserviço de calendário
    └── gamification-service/ # Código do microserviço de XP/Metas
```

---

## 🔒 Variáveis de Ambiente e Configurações locais

*   **`.env`**:
    ```env
    OBSIDIAN_VAULT_PATH=/home/elvenworks24/lucas-notes
    ```
*   **`config.json`**:
    Armazena dados mutáveis (URLs de iCal privadas, habits configurados, goals de carreira). É montado como volume no container `gamification-service` para persistência no host.

---

## 🚀 Como Executar
1.  Para ligar a stack (builda e roda em background tailando logs do Gateway):
    ```bash
    ./start.sh
    ```
2.  Para parar a stack:
    ```bash
    docker compose down
    ```

---

## 🔮 Backlog / Próximos Passos recomendados
1.  **Monitoramento (LGTM Stack):** Integrar Prometheus e Grafana para coletar métricas internas dos microserviços.
2.  **Healthcheck:** Adicionar blocos de `healthcheck` no `docker-compose.yml` para garantir que o gateway Nginx só suba após as APIs estarem saudáveis.
3.  **Formulário de Metas no UI:** Permitir a edição das metas financeiras/de carreira direto pela interface do dashboard (salvando via `POST /api/financial`).
4.  **Auto-refresh:** Adicionar sincronização periódica (ex: a cada 5 min) no Javascript do frontend para atualizar hábitos e agendas sem recarregar a tela.
