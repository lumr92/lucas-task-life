import os
import json
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Body, HTTPException
import requests

app = FastAPI(title="Lucas_OS Gamification Service", version="2.0.0")

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(PROJECT_DIR, "config.json")
VAULT_SVC_URL = "http://vault-service:9001"

def load_config() -> Dict[str, Any]:
    default = {
        "obsidian_vault_path": "/vault", # default container mount path
        "google_calendar_ical_url": "",
        "outlook_calendar_ical_url": "",
        "habits": ["agua", "exercicio", "estudos", "meditacao"],
        "study_plan_path": "03_Recursos/Estudos/# DevOps Study Plan — 30 - 60 - 90 Days.md",
        "manifesto_path": "manifesto.md",
        "character_name": "Lucas",
        "financial_goals": [
            {"label": "Reserva de Emergência", "current": 0, "target": 30000, "unit": "R$"},
            {"label": "Certificação CKA", "current": 60, "target": 100, "unit": "%"},
            {"label": "Meta Salarial SRE Sênior", "current": 8000, "target": 15000, "unit": "R$"}
        ],
        "career_goals": [
            {"label": "Concluir Fase 3 do Study Plan", "done": False},
            {"label": "Obter certificação CKA", "done": False},
            {"label": "Contribuir para projeto open-source", "done": False},
            {"label": "Dominar stack LGTM em produção", "done": False}
        ]
    }
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=2, ensure_ascii=False)
        return default
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    for k, v in default.items():
        cfg.setdefault(k, v)
    return cfg

def save_config(config: Dict[str, Any]):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def calculate_level(xp: int) -> Dict[str, int]:
    level = 1
    xp_for_next = 100
    current_xp = xp
    while current_xp >= xp_for_next:
        current_xp -= xp_for_next
        level += 1
        xp_for_next = level * 100
    return {
        "level": level,
        "current_xp": current_xp,
        "next_level_xp": xp_for_next,
        "percentage": int((current_xp / xp_for_next) * 100) if xp_for_next > 0 else 0
    }

def get_rank(level: int) -> str:
    if level < 4:
        return "SRE_Rookie"
    elif level < 7:
        return "Incident_Responder"
    elif level < 11:
        return "K8s_Apprentice"
    elif level < 16:
        return "Platform_Engineer"
    elif level < 21:
        return "Observability_Wizard"
    elif level < 26:
        return "IaC_Architect"
    else:
        return "SRE_Principal"

def get_internal_vault_data() -> Dict[str, Any]:
    try:
        r = requests.get(f"{VAULT_SVC_URL}/internal/vault-data", timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"Error fetching vault data from vault-service: {e}")
    return {"daily_notes": [], "quests": {"active": [], "completed": []}}

# ─── API Endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/status")
def get_status():
    config = load_config()
    vault_data = get_internal_vault_data()
    daily_notes = vault_data.get("daily_notes", [])
    quests = vault_data.get("quests", {"active": [], "completed": []})
    
    today_str = date.today().strftime("%Y-%m-%d")
    today_note = next((n for n in daily_notes if n["date"] == today_str), None)
    
    tasks_xp = len(quests.get("completed", [])) * 50
    notes_xp = len(daily_notes) * 20
    habits_xp = sum(n["completed_count"] * 10 for n in daily_notes)
    streak_bonus = sum(30 for n in daily_notes if n["completed_count"] == n["total_habits"] and n["total_habits"] > 0)
    total_xp = 100 + tasks_xp + notes_xp + habits_xp + streak_bonus

    level_info = calculate_level(total_xp)

    # Streak calculation
    notes_by_date = {n["date"]: n for n in daily_notes}
    streak = 0
    for i in range(365):
        d = date.today() - timedelta(days=i)
        n = notes_by_date.get(d.strftime("%Y-%m-%d"))
        if n and n["completed_count"] > 0:
            streak += 1
        else:
            break

    return {
        "character": {
            "name": config.get("character_name", "Lucas"),
            "rank": get_rank(level_info["level"]),
            "level": level_info["level"],
            "total_xp": total_xp,
            "level_xp": level_info["current_xp"],
            "next_level_xp": level_info["next_level_xp"],
            "xp_percentage": level_info["percentage"],
            "streak": streak,
        },
        "stats": {
            "daily_notes_count": len(daily_notes),
            "active_quests": len(quests.get("active", [])),
            "completed_quests": len(quests.get("completed", [])),
            "habits_today": today_note["completed_count"] if today_note else 0,
            "habits_total": len(config["habits"]),
        }
    }

@app.get("/api/stats")
def get_stats():
    config = load_config()
    vault_data = get_internal_vault_data()
    daily_notes = vault_data.get("daily_notes", [])
    quests = vault_data.get("quests", {"active": [], "completed": []})
    
    notes_by_date = {n["date"]: n for n in daily_notes}
    
    tasks_xp = len(quests.get("completed", [])) * 50
    base_xp = 100

    series = []
    days_sorted = sorted(notes_by_date.keys())
    xp_running = base_xp + tasks_xp
    for day_str in days_sorted:
        n = notes_by_date[day_str]
        day_xp = 20 + n["completed_count"] * 10
        if n["completed_count"] == n["total_habits"] and n["total_habits"] > 0:
            day_xp += 30
        xp_running += day_xp
        series.append({
            "date": day_str,
            "xp": xp_running,
            "habits_pct": int((n["completed_count"] / n["total_habits"]) * 100) if n["total_habits"] > 0 else 0,
            "completed": n["completed_count"]
        })

    return {"series": series}

@app.get("/api/financial")
def get_financial():
    config = load_config()
    return {
        "financial_goals": config.get("financial_goals", []),
        "career_goals": config.get("career_goals", [])
    }

@app.post("/api/financial")
def update_financial(data: Dict[str, Any] = Body(...)):
    config = load_config()
    if "financial_goals" in data:
        config["financial_goals"] = data["financial_goals"]
    if "career_goals" in data:
        config["career_goals"] = data["career_goals"]
    save_config(config)
    return {"status": "success"}

@app.get("/api/settings")
def get_settings():
    return load_config()

@app.post("/api/settings")
def update_settings(data: Dict[str, Any] = Body(...)):
    config = load_config()
    for key in ["obsidian_vault_path", "google_calendar_ical_url",
                "outlook_calendar_ical_url", "manifesto_path", "character_name"]:
        if key in data:
            config[key] = data[key]
    if "habits" in data and isinstance(data["habits"], list):
        config["habits"] = data["habits"]
    save_config(config)
    return {"status": "success", "config": config}
