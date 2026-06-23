import os
import time
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, date
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import HTMLResponse

app = FastAPI(title="Lucas_OS Todo Service", version="1.0.0")

# Database configuration from environment variables
DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "lucas_todo")
DB_USER = os.getenv("POSTGRES_USER", "lucas_user")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "lucas_password")

def get_db_connection():
    # Retry logic
    retries = 10
    while retries > 0:
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASS
            )
            return conn
        except psycopg2.OperationalError as e:
            retries -= 1
            print(f"[Todo Service] Database connection failed. Retrying... ({retries} left). Error: {e}")
            time.sleep(2)
    raise Exception("Could not connect to the database after several retries.")

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if 'frequency' column exists in recurring_tasks
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name='recurring_tasks' AND column_name='frequency'
        );
    """)
    has_frequency = cursor.fetchone()[0]
    if not has_frequency:
        print("[Todo Service] Upgrading recurring_tasks table schema...")
        cursor.execute("DROP TABLE IF EXISTS recurring_tasks;")
        conn.commit()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS todo_tasks (
            id SERIAL PRIMARY KEY,
            day VARCHAR(10) NOT NULL,
            category VARCHAR(50) NOT NULL,
            task_text TEXT NOT NULL,
            done BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(day, category, task_text)
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recurring_tasks (
            id SERIAL PRIMARY KEY,
            frequency VARCHAR(50) NOT NULL DEFAULT 'weekly', -- 'weekly', 'monthly', 'interval'
            weekday INTEGER,
            day_of_month INTEGER,
            interval_days INTEGER,
            base_date VARCHAR(10),
            category VARCHAR(50) NOT NULL,
            task_text TEXT NOT NULL,
            UNIQUE(frequency, weekday, day_of_month, interval_days, base_date, category, task_text)
        );
    """)
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM recurring_tasks")
    count = cursor.fetchone()[0]
    if count == 0:
        # Seed initial routines
        cursor.execute("INSERT INTO recurring_tasks (frequency, weekday, category, task_text) VALUES ('weekly', 0, 'domestic', 'Limpar o quarto')")
        cursor.execute("INSERT INTO recurring_tasks (frequency, weekday, category, task_text) VALUES ('weekly', 2, 'domestic', 'Lavar roupa')")
        cursor.execute("INSERT INTO recurring_tasks (frequency, interval_days, base_date, category, task_text) VALUES ('interval', 15, '2026-06-22', 'domestic', 'Trocar lençóis da cama')")
        cursor.execute("INSERT INTO recurring_tasks (frequency, day_of_month, category, task_text) VALUES ('monthly', 1, 'domestic', 'Limpeza pesada da casa')")
        conn.commit()
        
    cursor.close()
    conn.close()
    print("[Todo Service] Database tables initialized successfully.")

# Run database setup on startup
try:
    init_db()
except Exception as err:
    print(f"[Todo Service] Startup database initialization error: {err}")

# Default daily tasks
DEFAULT_TASKS = {
    "work": [
        "Monitoramento & Alertas (LGTM Stack, Datadog/Grafana)",
        "Verificar Quests pendentes no Lucas_OS",
        "Daily Sync & Status Report"
    ],
    "domestic": [
        "Limpar caixas de areia dos gatos",
        "Trocar água das meninas",
        "Guardar roupas"
    ],
    "studies": [
        "Avançar no DevOps Study Plan",
        "Fazer Labs/Prática de Código",
        "Revisar e Documentar Aprendizados"
    ],
    "health": [
        "Beber 2L de água",
        "Exercício físico / Alongamento"
    ],
    "finance": [
        "Registrar despesas do dia",
        "Verificar saldo/faturas"
    ]
}

def db_get_or_create_tasks(day_str: str) -> Dict[str, list]:
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Check if we have tasks for today
    cursor.execute("SELECT COUNT(*) FROM todo_tasks WHERE day = %s", (day_str,))
    count = cursor.fetchone()["count"]
    
    if count == 0:
        # Determine day parameters
        try:
            query_date = datetime.strptime(day_str, "%Y-%m-%d").date()
            weekday = query_date.weekday()
            day_of_month = query_date.day
        except Exception:
            query_date = None
            weekday = None
            day_of_month = None
            
        # Get all recurring tasks
        cursor.execute("SELECT frequency, weekday, day_of_month, interval_days, base_date, category, task_text FROM recurring_tasks")
        all_routines = cursor.fetchall()
        
        # Filter matching routines
        matched_tasks = []
        for r in all_routines:
            freq = r["frequency"]
            if freq == "weekly" and weekday is not None and r["weekday"] == weekday:
                matched_tasks.append(r)
            elif freq == "monthly" and day_of_month is not None and r["day_of_month"] == day_of_month:
                matched_tasks.append(r)
            elif freq == "interval" and query_date is not None and r["interval_days"] and r["base_date"]:
                try:
                    base_date = datetime.strptime(r["base_date"], "%Y-%m-%d").date()
                    diff = (query_date - base_date).days
                    if diff >= 0 and diff % r["interval_days"] == 0:
                        matched_tasks.append(r)
                except Exception as e:
                    print(f"Error parsing base date for routine: {e}")
            
        # Group them
        day_defaults = {cat: list(tasks) for cat, tasks in DEFAULT_TASKS.items()}
        for r in matched_tasks:
            cat = r["category"]
            if cat in day_defaults:
                day_defaults[cat].append(r["task_text"])
                
        # Populate defaults
        for cat, tasks in day_defaults.items():
            for t in tasks:
                try:
                    cursor.execute(
                        "INSERT INTO todo_tasks (day, category, task_text, done) VALUES (%s, %s, %s, FALSE) ON CONFLICT DO NOTHING",
                        (day_str, cat, t)
                    )
                except Exception as e:
                    print(f"Error inserting default task: {e}")
        conn.commit()
        
    # Fetch all tasks for today
    cursor.execute("SELECT id, category, task_text, done FROM todo_tasks WHERE day = %s ORDER BY id ASC", (day_str,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    result = {"work": [], "domestic": [], "studies": [], "health": [], "finance": []}
    for row in rows:
        cat = row["category"]
        if cat in result:
            result[cat].append({
                "id": row["id"],
                "text": row["task_text"],
                "done": row["done"]
            })
    return result

# FastAPI routes

@app.get("/todo", response_class=HTMLResponse)
def get_todo_page():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "todo.html")
    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail="Template file todo.html not found.")
    with open(template_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content, status_code=200)

@app.get("/api/todo/tasks")
def get_tasks_endpoint(day: Optional[str] = None):
    if not day:
        day = date.today().strftime("%Y-%m-%d")
    try:
        return db_get_or_create_tasks(day)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/todo/tasks")
def add_task_endpoint(payload: Dict[str, Any] = Body(...)):
    day = payload.get("day")
    category = payload.get("category")
    text = payload.get("text")
    if not text or not category:
        raise HTTPException(status_code=400, detail="Missing text or category")
    if not day:
        day = date.today().strftime("%Y-%m-%d")
        
    if category not in ["work", "domestic", "studies", "health", "finance"]:
        raise HTTPException(status_code=400, detail="Invalid category")
        
    # Ensure day is initialized with defaults first
    db_get_or_create_tasks(day)
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            "INSERT INTO todo_tasks (day, category, task_text, done) VALUES (%s, %s, %s, FALSE) "
            "ON CONFLICT (day, category, task_text) DO UPDATE SET day=EXCLUDED.day RETURNING id, category, task_text, done",
            (day, category, text)
        )
        new_task = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "success", "task": {
            "id": new_task["id"],
            "category": new_task["category"],
            "text": new_task["task_text"],
            "done": new_task["done"]
        }}
    except Exception as e:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/todo/tasks/toggle")
def toggle_task_endpoint(payload: Dict[str, Any] = Body(...)):
    task_id = payload.get("id")
    text = payload.get("text")
    day = payload.get("day")
    value = payload.get("value")
    
    if task_id is None and not text:
        raise HTTPException(status_code=400, detail="Missing task id or text")
        
    if not day:
        day = date.today().strftime("%Y-%m-%d")
        
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if task_id is not None:
            # Toggle by ID
            cursor.execute("SELECT done, task_text FROM todo_tasks WHERE id = %s", (task_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Task not found")
            new_done = value if value is not None else (not row["done"])
            cursor.execute("UPDATE todo_tasks SET done = %s WHERE id = %s RETURNING id, task_text, done", (new_done, task_id))
            updated = cursor.fetchone()
        else:
            # Toggle by text & day
            cursor.execute("SELECT id, done, task_text FROM todo_tasks WHERE day = %s AND LOWER(task_text) = LOWER(%s)", (day, text.strip()))
            row = cursor.fetchone()
            if not row:
                cursor.execute("SELECT id, done, task_text FROM todo_tasks WHERE day = %s AND (LOWER(task_text) LIKE LOWER(%s) OR LOWER(%s) LIKE LOWER(task_text))", (day, f"%{text.strip()}%", text.strip()))
                row = cursor.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail="Task not found for this day")
                
            new_done = value if value is not None else (not row["done"])
            cursor.execute("UPDATE todo_tasks SET done = %s WHERE id = %s RETURNING id, task_text, done", (new_done, row["id"]))
            updated = cursor.fetchone()
            
        conn.commit()
        cursor.close()
        conn.close()
        return {
            "status": "success",
            "task": {
                "id": updated["id"],
                "text": updated["task_text"],
                "done": updated["done"]
            }
        }
    except HTTPException:
        cursor.close()
        conn.close()
        raise
    except Exception as e:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/todo/tasks/delete")
def delete_task_endpoint(payload: Dict[str, Any] = Body(...)):
    task_id = payload.get("id")
    text = payload.get("text")
    day = payload.get("day")
    
    if task_id is None and not text:
        raise HTTPException(status_code=400, detail="Missing task id or text")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if task_id is not None:
            cursor.execute("DELETE FROM todo_tasks WHERE id = %s", (task_id,))
        else:
            if not day:
                day = date.today().strftime("%Y-%m-%d")
            cursor.execute("DELETE FROM todo_tasks WHERE day = %s AND LOWER(task_text) = LOWER(%s)", (day, text.strip()))
            
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "success"}
    except Exception as e:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

# ─── Recurring Tasks (Routines) APIs ──────────────────────────────────────────

@app.get("/api/todo/routines")
def get_routines_endpoint():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT id, frequency, weekday, day_of_month, interval_days, base_date, category, task_text FROM recurring_tasks ORDER BY frequency DESC, weekday ASC, day_of_month ASC, id ASC")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except Exception as e:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/todo/routines")
def add_routine_endpoint(payload: Dict[str, Any] = Body(...)):
    frequency = payload.get("frequency", "weekly")
    category = payload.get("category")
    text = payload.get("text")
    
    if not category or not text:
        raise HTTPException(status_code=400, detail="Missing category or text")
    if category not in ["work", "domestic", "studies", "health", "finance"]:
        raise HTTPException(status_code=400, detail="Invalid category")
        
    weekday = payload.get("weekday")
    day_of_month = payload.get("day_of_month")
    interval_days = payload.get("interval_days")
    base_date = payload.get("base_date")
    
    if frequency == "weekly":
        if weekday is None or not (0 <= weekday <= 6):
            raise HTTPException(status_code=400, detail="Invalid weekday for weekly routine (must be 0-6)")
        day_of_month = None
        interval_days = None
        base_date = None
    elif frequency == "monthly":
        if day_of_month is None or not (1 <= day_of_month <= 31):
            raise HTTPException(status_code=400, detail="Invalid day_of_month for monthly routine (must be 1-31)")
        weekday = None
        interval_days = None
        base_date = None
    elif frequency == "interval":
        if interval_days is None or interval_days <= 0:
            raise HTTPException(status_code=400, detail="Invalid interval_days for interval routine (must be > 0)")
        if not base_date:
            base_date = date.today().strftime("%Y-%m-%d")
        try:
            datetime.strptime(base_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid base_date format (must be YYYY-MM-DD)")
        weekday = None
        day_of_month = None
    else:
        raise HTTPException(status_code=400, detail="Invalid frequency type")
        
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            "INSERT INTO recurring_tasks (frequency, weekday, day_of_month, interval_days, base_date, category, task_text) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (frequency, weekday, day_of_month, interval_days, base_date, category, task_text) "
            "DO UPDATE SET task_text=EXCLUDED.task_text "
            "RETURNING id, frequency, weekday, day_of_month, interval_days, base_date, category, task_text",
            (frequency, weekday, day_of_month, interval_days, base_date, category, text)
        )
        new_r = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "success", "routine": new_r}
    except Exception as e:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/todo/routines/delete")
def delete_routine_endpoint(payload: Dict[str, Any] = Body(...)):
    routine_id = payload.get("id")
    if routine_id is None:
        raise HTTPException(status_code=400, detail="Missing routine id")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM recurring_tasks WHERE id = %s", (routine_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "success"}
    except Exception as e:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

