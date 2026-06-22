import os
import re
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
import frontmatter
from fastapi import FastAPI, HTTPException, Body
import requests

app = FastAPI(title="Lucas_OS Vault Service", version="2.0.0")

VAULT_PATH = "/vault"
GAMIFICATION_SVC_URL = "http://gamification-service:9003"

def get_settings_from_gami() -> Dict[str, Any]:
    try:
        r = requests.get(f"{GAMIFICATION_SVC_URL}/api/settings", timeout=2)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"Error fetching settings: {e}")
    return {
        "habits": ["agua", "exercicio", "estudos", "meditacao"],
        "study_plan_path": "03_Recursos/Estudos/# DevOps Study Plan — 30 - 60 - 90 Days.md",
        "manifesto_path": "manifesto.md"
    }

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
        # Start from the Monday of 3 weeks ago (to include the current week)
        start = today - timedelta(days=today.weekday() + 21)
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

# ─── Study Plan Parser ────────────────────────────────────────────────────────

def parse_study_plan(vault_path: str, relative_path: str) -> Dict[str, Any]:
    filepath = os.path.join(vault_path, relative_path)
    if not os.path.exists(filepath):
        return {"phases": [], "error": f"Study plan file not found: {relative_path}"}

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        phases = []
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

            topics = []
            for line in chunk.splitlines():
                s = line.strip()
                if s.startswith("- [x]") or s.startswith("- [ ]"):
                    text = s[5:].strip()
                    text = re.sub(r"✅ \d{4}-\d{2}-\d{2}$", "", text).strip()
                    if text:
                        topics.append({"text": text, "done": s.startswith("- [x]")})

            phases.append({
                "name": phase_name,
                "done": done,
                "pending": pending,
                "total": total,
                "percentage": pct,
                "topics": topics[:20]
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
        post = frontmatter.loads(content)
        text = post.content
        lines = [
            l.strip().lstrip(">").strip()
            for l in text.splitlines()
            if l.strip() and not l.strip().startswith("#") and not l.strip().startswith("---")
        ]
        lines = [l for l in lines if l][:6]
        return {"lines": lines if lines else fallback, "source": relative_path}
    except Exception as e:
        return {"lines": fallback, "source": "default", "error": str(e)}

# ─── API Endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/habits")
def get_habits():
    settings = get_settings_from_gami()
    parser = VaultParser(VAULT_PATH, settings["habits"])
    return parser.get_habits_weekly()

@app.get("/api/quests")
def get_quests():
    settings = get_settings_from_gami()
    parser = VaultParser(VAULT_PATH, settings["habits"])
    quests = parser.get_all_quests()
    return {
        "active": quests["active"],
        "completed": quests["completed"][:20]
    }

@app.get("/api/projects")
def get_projects():
    settings = get_settings_from_gami()
    parser = VaultParser(VAULT_PATH, settings["habits"])
    return {"projects": parser.get_projects()}

@app.get("/api/study-plan")
def get_study_plan():
    settings = get_settings_from_gami()
    return parse_study_plan(VAULT_PATH, settings["study_plan_path"])

@app.get("/api/manifesto")
def get_manifesto_endpoint():
    settings = get_settings_from_gami()
    return get_manifesto(VAULT_PATH, settings.get("manifesto_path", "manifesto.md"))

@app.post("/api/quests/toggle")
def toggle_quest(payload: Dict[str, str] = Body(...)):
    quest_id = payload.get("id")
    if not quest_id:
        raise HTTPException(status_code=400, detail="Missing quest id")
    try:
        parts = quest_id.rsplit(":", 1)
        rel_path, line_idx = parts[0], int(parts[1])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid quest ID: {e}")
    filepath = os.path.join(VAULT_PATH, rel_path)
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

@app.post("/api/habits/toggle")
def toggle_habit(payload: Dict[str, Any] = Body(...)):
    habit = payload.get("habit")
    day_str = payload.get("day")
    explicit_val = payload.get("value")
    
    if not habit:
        raise HTTPException(status_code=400, detail="Missing habit name")
    
    if not day_str:
        day_str = date.today().strftime("%Y-%m-%d")
        
    daily_dir = os.path.join(VAULT_PATH, "00_Diario")
    os.makedirs(daily_dir, exist_ok=True)
    note_path = os.path.join(daily_dir, f"{day_str}.md")
    
    # If daily note doesn't exist, create it from template
    if not os.path.exists(note_path):
        template_path = os.path.join(VAULT_PATH, "99_Modelos/template-diario.md")
        template_content = ""
        if os.path.exists(template_path):
            try:
                with open(template_path, "r", encoding="utf-8") as tf:
                    template_content = tf.read()
                # Replacements
                template_content = template_content.replace('<% tp.date.now("YYYY-MM-DD") %>', day_str)
                template_content = template_content.replace('{{date:YYYY-MM-DD}}', day_str)
                template_content = re.sub(r"<%[\s\S]*?%>", "", template_content)
            except Exception as e:
                print(f"Error reading template: {e}")
        
        try:
            with open(note_path, "w", encoding="utf-8") as nf:
                nf.write(template_content)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create daily note: {e}")
            
    try:
        post = frontmatter.load(note_path)
        current_val = post.get(habit, False)
        is_done = str(current_val).lower() in ["true", "yes", "1", "y"]
        
        new_val = explicit_val if explicit_val is not None else (not is_done)
        post[habit] = new_val
        
        with open(note_path, "w", encoding="utf-8") as f:
            f.write(frontmatter.dumps(post))
            
        return {"status": "success", "habit": habit, "new_state": new_state, "day": day_str}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update habit: {e}")

@app.post("/api/quests/toggle-text")
def toggle_quest_by_text(payload: Dict[str, Any] = Body(...)):
    text_to_find = payload.get("text")
    day_str = payload.get("day")
    explicit_val = payload.get("value")
    
    if not text_to_find:
        raise HTTPException(status_code=400, detail="Missing text to toggle")
        
    if not day_str:
        day_str = date.today().strftime("%Y-%m-%d")
        
    daily_dir = os.path.join(VAULT_PATH, "00_Diario")
    os.makedirs(daily_dir, exist_ok=True)
    note_path = os.path.join(daily_dir, f"{day_str}.md")
    
    # If daily note doesn't exist, create it from template
    if not os.path.exists(note_path):
        template_path = os.path.join(VAULT_PATH, "99_Modelos/template-diario.md")
        template_content = ""
        if os.path.exists(template_path):
            try:
                with open(template_path, "r", encoding="utf-8") as tf:
                    template_content = tf.read()
                # Replacements
                template_content = template_content.replace('<% tp.date.now("YYYY-MM-DD") %>', day_str)
                template_content = template_content.replace('{{date:YYYY-MM-DD}}', day_str)
                template_content = re.sub(r"<%[\s\S]*?%>", "", template_content)
            except Exception as e:
                print(f"Error reading template: {e}")
        
        try:
            with open(note_path, "w", encoding="utf-8") as nf:
                nf.write(template_content)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create daily note: {e}")
            
    try:
        with open(note_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        found = False
        new_state = False
        for idx, line in enumerate(lines):
            if ("- [ ]" in line or "- [x]" in line) and text_to_find.lower() in line.lower():
                is_done = "- [x]" in line
                new_state = explicit_val if explicit_val is not None else (not is_done)
                new_box = "- [x]" if new_state else "- [ ]"
                lines[idx] = re.sub(r"- \[[ x]\]", new_box, line, count=1)
                found = True
                break
                
        if not found:
            # If the task is not found in the file, append it under Rotina Doméstica or at the bottom
            # Let's try to append it under "## 🧺 Rotina Doméstica" if that section exists
            section_idx = -1
            for idx, line in enumerate(lines):
                if "## 🧺 Rotina Doméstica" in line:
                    section_idx = idx
                    break
            
            new_box = "- [x]" if explicit_val is True or explicit_val is None else "- [ ]"
            new_line = f"{new_box} {text_to_find}\n"
            
            if section_idx != -1:
                lines.insert(section_idx + 1, new_line)
                new_state = (explicit_val is True or explicit_val is None)
            else:
                lines.append(f"\n{new_line}")
                new_state = (explicit_val is True or explicit_val is None)
            
        with open(note_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
            
        return {"status": "success", "text": text_to_find, "new_state": new_state}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to toggle quest text: {e}")

# ─── Internal API ─────────────────────────────────────────────────────────────

@app.get("/internal/vault-data")
def get_internal_vault_data():
    settings = get_settings_from_gami()
    parser = VaultParser(VAULT_PATH, settings["habits"])
    daily_notes = parser.get_daily_notes()
    quests = parser.get_all_quests()
    return {
        "daily_notes": daily_notes,
        "quests": quests
    }
