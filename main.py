import os
import re
import json
import glob
import math
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
import frontmatter
from fastapi import FastAPI, HTTPException, Body, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import requests
from icalendar import Calendar as iCal
import recurring_ical_events

app = FastAPI(title="Lucas_OS Backend", version="2.0.0")

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(PROJECT_DIR, "config.json")

os.makedirs(os.path.join(PROJECT_DIR, "static"), exist_ok=True)
os.makedirs(os.path.join(PROJECT_DIR, "templates"), exist_ok=True)

app.mount("/static", StaticFiles(directory=os.path.join(PROJECT_DIR, "static")), name="static")


# ─── Config ───────────────────────────────────────────────────────────────────

def load_config() -> Dict[str, Any]:
    default = {
        "obsidian_vault_path": "/home/elvenworks24/lucas-notes",
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
    # merge missing keys
    for k, v in default.items():
        cfg.setdefault(k, v)
    return cfg


def save_config(config: Dict[str, Any]):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


# ─── Gamification ─────────────────────────────────────────────────────────────

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


# ─── Vault Parser ─────────────────────────────────────────────────────────────

class VaultParser:
    def __init__(self, vault_path: str, habits_list: List[str]):
        self.vault_path = vault_path
        self.habits_list = habits_list

    def get_daily_notes(self) -> List[Dict[str, Any]]:
        daily_dir = os.path.join(self.vault_path, "00_Diario")
        if not os.path.exists(daily_dir):
            return []
        notes = []
        pattern = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")
        for filename in os.listdir(daily_dir):
            if not pattern.match(filename):
                continue
            date_str = filename[:-3]
            filepath = os.path.join(daily_dir, filename)
            try:
                post = frontmatter.load(filepath)
                habits_status = {}
                completed_count = 0
                for habit in self.habits_list:
                    val = post.get(habit, False)
                    is_done = str(val).lower() in ["true", "yes", "1", "y"]
                    habits_status[habit] = is_done
                    if is_done:
                        completed_count += 1
                notes.append({
                    "date": date_str,
                    "habits": habits_status,
                    "completed_count": completed_count,
                    "total_habits": len(self.habits_list),
                    "content_preview": post.content[:200] if post.content else ""
                })
            except Exception as e:
                print(f"Error parsing {filename}: {e}")
        notes.sort(key=lambda x: x["date"], reverse=True)
        return notes

    def get_habits_weekly(self) -> Dict[str, Any]:
        """Return habit data structured as weeks (last 4 weeks)."""
        notes_list = self.get_daily_notes()
        notes_by_date = {n["date"]: n for n in notes_list}
        today = date.today()

        # Calculate streak
        streak = 0
        for i in range(0, 365):
            d = today - timedelta(days=i)
            note = notes_by_date.get(d.strftime("%Y-%m-%d"))
            if note and note["completed_count"] > 0:
                streak += 1
            else:
                break

        # Build last 4 weeks grid
        weeks = []
        # Start from the Monday of 4 weeks ago
        start = today - timedelta(days=today.weekday() + 28)
        for week_num in range(4):
            week_days = []
            for day_offset in range(7):
                d = start + timedelta(days=week_num * 7 + day_offset)
                d_str = d.strftime("%Y-%m-%d")
                note = notes_by_date.get(d_str)
                if note:
                    week_days.append({
                        "date": d_str,
                        "weekday": d.strftime("%a"),
                        "habits": note["habits"],
                        "completed": note["completed_count"],
                        "total": note["total_habits"],
                        "has_note": True,
                        "is_today": d == today
                    })
                else:
                    week_days.append({
                        "date": d_str,
                        "weekday": d.strftime("%a"),
                        "habits": {h: False for h in self.habits_list},
                        "completed": 0,
                        "total": len(self.habits_list),
                        "has_note": False,
                        "is_today": d == today
                    })
            weeks.append(week_days)

        return {
            "habits_list": self.habits_list,
            "weeks": weeks,
            "streak": streak,
            "today": today.strftime("%Y-%m-%d")
        }

    def get_all_quests(self) -> Dict[str, List[Dict[str, Any]]]:
        active, completed = [], []
        ignored = {".git", ".obsidian", "_attachments"}
        for root, dirs, files in os.walk(self.vault_path):
            dirs[:] = [d for d in dirs if d not in ignored]
            for file in files:
                if not file.endswith(".md"):
                    continue
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, self.vault_path)
                category = "Geral"
                if "01_Projetos" in rel_path:
                    category = "Projetos"
                elif "02_Areas" in rel_path:
                    category = "Trabalho"
                elif "03_Recursos" in rel_path:
                    category = "Estudos"
                elif "00_Diario" in rel_path:
                    category = "Diário"
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    for idx, line in enumerate(lines):
                        s = line.strip()
                        if s.startswith("- [ ]") or s.startswith("- [x]"):
                            is_done = s.startswith("- [x]")
                            text = s[5:].strip()
                            if not text:
                                continue
                            q = {
                                "id": f"{rel_path}:{idx}",
                                "text": text,
                                "file": file[:-3],
                                "path": rel_path,
                                "category": category,
                                "line": idx + 1
                            }
                            (completed if is_done else active).append(q)
                except Exception as e:
                    print(f"Error reading {rel_path}: {e}")
        return {"active": active, "completed": completed}

    def get_projects(self) -> List[Dict[str, Any]]:
        projects_dir = os.path.join(self.vault_path, "01_Projetos")
        if not os.path.exists(projects_dir):
            return []
        projects = []
        for filename in os.listdir(projects_dir):
            if not filename.endswith(".md"):
                continue
            filepath = os.path.join(projects_dir, filename)
            name = filename[:-3]
            active_tasks, done_tasks = 0, 0
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                active_tasks = len(re.findall(r"^- \[ \]", content, re.MULTILINE))
                done_tasks = len(re.findall(r"^- \[x\]", content, re.MULTILINE))
            except Exception:
                pass
            projects.append({
                "name": name,
                "file": filename,
                "path": f"01_Projetos/{filename}",
                "active_tasks": active_tasks,
                "done_tasks": done_tasks,
                "status": "active" if active_tasks > 0 else ("completed" if done_tasks > 0 else "empty")
            })
        return projects

    def get_stats_series(self) -> Dict[str, Any]:
        """Return time series for charts: last 60 days."""
        notes_list = self.get_daily_notes()
        notes_by_date = {n["date"]: n for n in notes_list}
        today = date.today()

        # XP calculation helper (same logic as /api/status)
        quests = self.get_all_quests()
        tasks_xp = len(quests["completed"]) * 50
        notes_xp_acc = 0
        habits_xp_acc = 0
        streak_bonus_acc = 0
        base_xp = 100

        series = []
        cumulative_xp = base_xp + tasks_xp

        # Build day by day (ascending)
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


# ─── Study Plan Parser ────────────────────────────────────────────────────────

def parse_study_plan(vault_path: str, relative_path: str) -> Dict[str, Any]:
    filepath = os.path.join(vault_path, relative_path)
    if not os.path.exists(filepath):
        return {"phases": [], "error": "Study plan file not found"}

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        phases = []
        # Split by phase headings (## Fase N)
        phase_pattern = re.compile(r"## (Fase \d+ —[^\n]+)", re.IGNORECASE)
        phase_matches = list(phase_pattern.finditer(content))

        for i, match in enumerate(phase_matches):
            phase_name = match.group(1).strip()
            start = match.end()
            end = phase_matches[i + 1].start() if i + 1 < len(phase_matches) else len(content)
            chunk = content[start:end]

            done = len(re.findall(r"^- \[x\]", chunk, re.MULTILINE))
            pending = len(re.findall(r"^- \[ \]", chunk, re.MULTILINE))
            total = done + pending
            pct = int((done / total) * 100) if total > 0 else 0

            # Extract topics
            topics = []
            for line in chunk.splitlines():
                s = line.strip()
                if s.startswith("- [x]") or s.startswith("- [ ]"):
                    text = s[5:].strip()
                    # Remove date annotation at end
                    text = re.sub(r"✅ \d{4}-\d{2}-\d{2}$", "", text).strip()
                    if text:
                        topics.append({"text": text, "done": s.startswith("- [x]")})

            phases.append({
                "name": phase_name,
                "done": done,
                "pending": pending,
                "total": total,
                "percentage": pct,
                "topics": topics[:20]  # limit for UI
            })

        overall_done = sum(p["done"] for p in phases)
        overall_total = sum(p["total"] for p in phases)

        return {
            "phases": phases,
            "overall_done": overall_done,
            "overall_total": overall_total,
            "overall_percentage": int((overall_done / overall_total) * 100) if overall_total > 0 else 0
        }
    except Exception as e:
        return {"phases": [], "error": str(e)}


# ─── Manifesto Parser ─────────────────────────────────────────────────────────

def get_manifesto(vault_path: str, relative_path: str) -> Dict[str, Any]:
    filepath = os.path.join(vault_path, relative_path)
    fallback = [
        "Sistemas confiáveis são construídos por pessoas disciplinadas.",
        "Automatize o toil. Libere tempo para pensar.",
        "Observabilidade não é opcional em produção.",
        "Você é o projeto mais importante que vai gerenciar."
    ]
    if not os.path.exists(filepath):
        return {"lines": fallback, "source": "default"}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        # Remove frontmatter if any
        post = frontmatter.loads(content)
        text = post.content
        # Extract non-empty, non-header lines
        lines = [
            l.strip().lstrip(">").strip()
            for l in text.splitlines()
            if l.strip() and not l.strip().startswith("#") and not l.strip().startswith("---")
        ]
        lines = [l for l in lines if l][:6]
        return {"lines": lines if lines else fallback, "source": relative_path}
    except Exception as e:
        return {"lines": fallback, "source": "default", "error": str(e)}


# ─── Calendar ─────────────────────────────────────────────────────────────────

def extract_meeting_url(description: str, location: str) -> Optional[str]:
    for text in [location, description]:
        if not text:
            continue
        m = re.search(r'https://teams\.microsoft\.com/[^\s<>"]+', text)
        if m:
            return m.group(0)
        m = re.search(r'https://meet\.google\.com/[a-z]{3}-[a-z]{4}-[a-z]{3}', text)
        if m:
            return m.group(0)
        m = re.search(r'https://[a-zA-Z0-9-]+\.zoom\.us/j/[^\s<>"]+', text)
        if m:
            return m.group(0)
    return None


def fetch_and_parse_ical(url: str, label: str) -> List[Dict[str, Any]]:
    if not url:
        return []
    try:
        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            return []
        gcal = iCal.from_ical(response.content)
        now = datetime.now()
        start_of_today = datetime.combine(date.today(), datetime.min.time())
        thirty_days = now + timedelta(days=30)
        ical_events = recurring_ical_events.of(gcal).between(start_of_today, thirty_days)
        events = []
        for comp in ical_events:
            dtstart = comp.get("dtstart")
            if not dtstart:
                continue
            dt = dtstart.dt
            is_all_day = not isinstance(dt, datetime)
            if is_all_day:
                start_dt = datetime.combine(dt, datetime.min.time())
            else:
                start_dt = dt.astimezone().replace(tzinfo=None) if dt.tzinfo else dt
            if not (start_of_today <= start_dt <= thirty_days):
                continue
            summary = str(comp.get("summary", "Sem título"))
            description = str(comp.get("description", ""))
            location = str(comp.get("location", ""))
            events.append({
                "summary": summary,
                "start": start_dt.strftime("%Y-%m-%d %H:%M"),
                "start_raw": start_dt,
                "all_day": is_all_day,
                "description": description,
                "location": location,
                "source": label,
                "meeting_url": extract_meeting_url(description, location)
            })
        return events
    except Exception as e:
        print(f"Error fetching {label}: {e}")
        return []


def get_mock_events() -> List[Dict[str, Any]]:
    today = date.today()
    return [
        {
            "summary": "Deploy Kubernetes Prod ☸️",
            "start": f"{today} 10:00",
            "start_raw": datetime.combine(today, datetime.min.time()) + timedelta(hours=10),
            "all_day": False, "description": "Rolling update sem downtime",
            "location": "", "source": "Google Calendar (demo)", "meeting_url": None
        },
        {
            "summary": "1:1 Engineering Sync 🤝",
            "start": f"{today + timedelta(days=1)} 14:00",
            "start_raw": datetime.combine(today + timedelta(days=1), datetime.min.time()) + timedelta(hours=14),
            "all_day": False, "description": "Alinhamento semanal",
            "location": "", "source": "Outlook (demo)",
            "meeting_url": "https://teams.microsoft.com/l/meetup-join/demo"
        },
        {
            "summary": "Estudar LGTM Stack 📊",
            "start": f"{today + timedelta(days=2)} 20:00",
            "start_raw": datetime.combine(today + timedelta(days=2), datetime.min.time()) + timedelta(hours=20),
            "all_day": False, "description": "Loki, Grafana, Tempo, Mimir",
            "location": "", "source": "Google Calendar (demo)", "meeting_url": None
        },
    ]


# ─── API Endpoints ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def get_dashboard(request: Request):
    templates = Jinja2Templates(directory=os.path.join(PROJECT_DIR, "templates"))
    return templates.TemplateResponse(request, "index.html")


@app.get("/api/status")
def get_status():
    config = load_config()
    parser = VaultParser(config["obsidian_vault_path"], config["habits"])
    daily_notes = parser.get_daily_notes()
    quests = parser.get_all_quests()
    today_str = date.today().strftime("%Y-%m-%d")
    today_note = next((n for n in daily_notes if n["date"] == today_str), None)

    tasks_xp = len(quests["completed"]) * 50
    notes_xp = len(daily_notes) * 20
    habits_xp = sum(n["completed_count"] * 10 for n in daily_notes)
    streak_bonus = sum(30 for n in daily_notes if n["completed_count"] == n["total_habits"] and n["total_habits"] > 0)
    total_xp = 100 + tasks_xp + notes_xp + habits_xp + streak_bonus

    level_info = calculate_level(total_xp)

    # Streak
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
            "active_quests": len(quests["active"]),
            "completed_quests": len(quests["completed"]),
            "habits_today": today_note["completed_count"] if today_note else 0,
            "habits_total": len(config["habits"]),
        }
    }


@app.get("/api/habits")
def get_habits():
    config = load_config()
    parser = VaultParser(config["obsidian_vault_path"], config["habits"])
    return parser.get_habits_weekly()


@app.get("/api/quests")
def get_quests():
    config = load_config()
    parser = VaultParser(config["obsidian_vault_path"], config["habits"])
    quests = parser.get_all_quests()
    return {
        "active": quests["active"],
        "completed": quests["completed"][:20]
    }


@app.get("/api/projects")
def get_projects():
    config = load_config()
    parser = VaultParser(config["obsidian_vault_path"], config["habits"])
    return {"projects": parser.get_projects()}


@app.get("/api/study-plan")
def get_study_plan():
    config = load_config()
    return parse_study_plan(config["obsidian_vault_path"], config["study_plan_path"])


@app.get("/api/manifesto")
def get_manifesto_endpoint():
    config = load_config()
    return get_manifesto(config["obsidian_vault_path"], config.get("manifesto_path", "manifesto.md"))


@app.get("/api/calendar")
def get_calendar():
    config = load_config()
    events = []
    google_url = config.get("google_calendar_ical_url", "")
    outlook_url = config.get("outlook_calendar_ical_url", "")
    has_real = False
    if google_url:
        events.extend(fetch_and_parse_ical(google_url, "Google Calendar"))
        has_real = True
    if outlook_url:
        events.extend(fetch_and_parse_ical(outlook_url, "Outlook"))
        has_real = True
    if not has_real:
        events = get_mock_events()
    events.sort(key=lambda x: x["start_raw"])
    for e in events:
        e.pop("start_raw", None)
    return events[:15]


@app.get("/api/stats")
def get_stats():
    config = load_config()
    parser = VaultParser(config["obsidian_vault_path"], config["habits"])
    return parser.get_stats_series()


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


@app.post("/api/quests/toggle")
def toggle_quest(payload: Dict[str, str] = Body(...)):
    quest_id = payload.get("id")
    if not quest_id:
        raise HTTPException(status_code=400, detail="Missing quest id")
    config = load_config()
    vault_path = config["obsidian_vault_path"]
    try:
        parts = quest_id.rsplit(":", 1)
        rel_path, line_idx = parts[0], int(parts[1])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid quest ID: {e}")
    filepath = os.path.join(vault_path, rel_path)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if line_idx < 0 or line_idx >= len(lines):
            raise HTTPException(status_code=400, detail="Line out of bounds")
        line = lines[line_idx]
        if "- [ ]" in line:
            lines[line_idx] = line.replace("- [ ]", "- [x]", 1)
            new_state = "completed"
        elif "- [x]" in line:
            lines[line_idx] = line.replace("- [x]", "- [ ]", 1)
            new_state = "active"
        else:
            raise HTTPException(status_code=400, detail="Not a checkbox line")
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return {"status": "success", "new_state": new_state}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=9999)
