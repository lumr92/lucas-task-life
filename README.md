# Lucas_OS — SRE Dashboard

Dashboard pessoal gamificado para SRE Engineer, integrado ao Obsidian vault.

Inspirado no **RETRO_OS** do Tuca, adaptado para o contexto de um SRE com foco em produtividade, hábitos, estudo e carreira.

## ✨ Features

| Aba | O que faz |
|---|---|
| **HOME** | Identidade, XP/Level, Streak, Manifesto, Status dos sistemas |
| **ESTUDOS** | Progresso real do Study Plan 30-60-90 days (lê o Obsidian) |
| **PROJETOS** | Board de projetos + Quest Board com toggle done/undone |
| **ROTINA** | Grade semanal de hábitos (lê YAML frontmatter das notas diárias) |
| **AGENDA** | Timeline de eventos Google Calendar + Outlook (via iCal) |
| **STATS** | Gráficos de XP e consistência de hábitos (Canvas API nativo) |
| **FINANCEIRO** | Metas financeiras e goals de carreira SRE |

## 🛠️ Stack

- **Backend**: Python + FastAPI + Uvicorn
- **Frontend**: HTML + CSS + JavaScript puros (sem Node/npm)
- **Fontes**: Space Grotesk + JetBrains Mono (Google Fonts)
- **Dados**: Leitura direta do vault Obsidian (`.md` files) + feeds iCal

## 🚀 Como rodar

```bash
git clone https://github.com/lumr92/lucas-task-life.git
cd lucas-task-life

# 1. Copie o template de configuração e edite com seus dados
cp config.example.json config.json
# Edite config.json: defina o path do vault, URLs do calendário, etc.

# 2. Inicie o servidor (cria o venv automaticamente na primeira vez)
./start.sh
```

Acesse: **http://127.0.0.1:9999**

## ⚙️ Configuração

Edite o `config.json` na raiz do projeto:

```json
{
  "obsidian_vault_path": "/caminho/para/seu/vault",
  "google_calendar_ical_url": "https://calendar.google.com/...",
  "outlook_calendar_ical_url": "https://outlook.office365.com/...",
  "habits": ["agua", "exercicio", "estudos", "meditacao"],
  "study_plan_path": "caminho/relativo/ao/study-plan.md",
  "manifesto_path": "manifesto.md",
  "financial_goals": [
    {"label": "Reserva de Emergência", "current": 0, "target": 30000, "unit": "R$"}
  ],
  "career_goals": [
    {"label": "Obter certificação CKA", "done": false}
  ]
}
```

### Hábitos no Obsidian

Nas notas diárias (`00_Diario/YYYY-MM-DD.md`), adicione frontmatter YAML:

```yaml
---
agua: true
exercicio: false
estudos: true
meditacao: true
---
```

## 📁 Estrutura

```
lumina-quest/
├── main.py           # Backend FastAPI (APIs + parsers)
├── config.json       # Configuração central
├── requirements.txt  # Dependências Python
├── start.sh          # Script de inicialização
├── templates/
│   └── index.html    # SPA com 7 abas
└── static/
    ├── style.css     # Design system (paleta azul, scan lines)
    └── app.js        # Lógica frontend + Canvas charts
```

## 🔌 Endpoints da API

| Endpoint | Método | Descrição |
|---|---|---|
| `/api/status` | GET | XP, level, rank, streak |
| `/api/habits` | GET | Grade semanal de hábitos |
| `/api/quests` | GET | Tarefas ativas e concluídas |
| `/api/quests/toggle` | POST | Marca/desmarca tarefa no vault |
| `/api/projects` | GET | Projetos de `01_Projetos/` |
| `/api/study-plan` | GET | Progresso do study plan |
| `/api/manifesto` | GET | Frases da nota manifesto |
| `/api/calendar` | GET | Eventos dos próximos 30 dias |
| `/api/stats` | GET | Série temporal XP e hábitos |
| `/api/financial` | GET/POST | Metas financeiras e carreira |
| `/api/settings` | GET/POST | Lê e salva config.json |
