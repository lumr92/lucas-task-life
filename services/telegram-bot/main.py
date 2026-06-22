import os
import time
import json
import re
import threading
from datetime import datetime
import requests

TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

VAULT_SVC_URL = "http://vault-service:9001"
GAMIFICATION_SVC_URL = "http://gamification-service:9003"

EMOJIS = {
    "agua": "💧",
    "exercicio": "🏋️",
    "estudos": "📚",
    "meditacao": "🧘",
    "atividades de casa": "🧺"
}

def get_emoji(habit_name: str) -> str:
    return EMOJIS.get(habit_name.lower().replace("_", " "), "⚡")

# ─── API Helpers ──────────────────────────────────────────────────────────────

def send_telegram(method: str, payload: dict) -> dict:
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.json()
    except Exception as e:
        print(f"[Telegram Bot] Error calling {method}: {e}")
        return {}

def send_message(text: str, reply_markup: dict = None) -> dict:
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return send_telegram("sendMessage", payload)

def edit_message(message_id: int, text: str, reply_markup: dict = None) -> dict:
    payload = {
        "chat_id": CHAT_ID,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return send_telegram("editMessageText", payload)

# ─── Data Helpers ─────────────────────────────────────────────────────────────

def get_today_habits() -> dict:
    try:
        r = requests.get(f"{VAULT_SVC_URL}/api/habits", timeout=5)
        if r.status_code == 200:
            data = r.json()
            for week in data.get("weeks", []):
                for day in week:
                    if day.get("is_today", False):
                        return day.get("habits", {})
    except Exception as e:
        print(f"[Telegram Bot] Error fetching today's habits: {e}")
    return {}

def get_active_quests_formatted() -> str:
    try:
        r = requests.get(f"{VAULT_SVC_URL}/api/quests", timeout=5)
        if r.status_code == 200:
            data = r.json()
            active = data.get("active", [])
            if not active:
                return "🎉 Todas as suas quests foram concluídas!"
            
            lines = [f"⚔️ <b>Quests Ativas ({len(active)}):</b>"]
            for idx, q in enumerate(active[:8]):
                lines.append(f"{idx+1}. [{q['category']}] {q['text']} <i>({q['file']})</i>")
            if len(active) > 8:
                lines.append(f"...e mais {len(active) - 8} quests pendentes.")
            return "\n".join(lines)
    except Exception as e:
        print(f"[Telegram Bot] Error fetching quests: {e}")
    return "⚠️ Erro ao comunicar com o vault-service."

def get_status_formatted() -> str:
    try:
        r = requests.get(f"{GAMIFICATION_SVC_URL}/api/status", timeout=5)
        if r.status_code == 200:
            data = r.json()
            char = data.get("character", {})
            stats = data.get("stats", {})
            
            # Formata barra de XP
            pct = char.get("xp_percentage", 0)
            bars = int(pct / 10)
            xp_bar = "🟢" * bars + "⚪" * (10 - bars)
            
            return (
                f"👤 <b>Ficha de SRE: {char.get('name')}</b>\n"
                f"───────────────────\n"
                f"🛡️ Rank: <code>{char.get('rank')}</code>\n"
                f"⭐ Nível: {char.get('level')}\n"
                f"🔥 Streak: {char.get('streak')} dias\n"
                f"📊 XP: {char.get('total_xp')} total ({pct}%)\n"
                f"[{xp_bar}]\n\n"
                f"📝 Notas Diárias: {stats.get('daily_notes_count')}\n"
                f"⚔️ Quests Concluídas: {stats.get('completed_quests')}\n"
                f"💧 Hábitos Hoje: {stats.get('habits_today')}/{stats.get('habits_total')}"
            )
    except Exception as e:
        print(f"[Telegram Bot] Error fetching SRE status: {e}")
    return "⚠️ Erro ao comunicar com o gamification-service."

def get_daily_tasks_data() -> dict:
    try:
        r = requests.get(f"{VAULT_SVC_URL}/api/daily-tasks", timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[Telegram Bot] Error fetching daily tasks: {e}")
    return {}

def get_routine_markup(category: str, tasks: list) -> dict:
    keyboard = []
    row = []
    for idx, t in enumerate(tasks):
        status_symbol = "✅" if t["done"] else "❌"
        btn_text = f"{idx + 1}: {status_symbol}"
        callback_data = f"toggle_task:{category}:{idx}"
        row.append({"text": btn_text, "callback_data": callback_data})
    keyboard.append(row)
    keyboard.append([{"text": "🏁 Concluir", "callback_data": f"finish_routine:{category}"}])
    return {"inline_keyboard": keyboard}

def get_habits_markup(habits_status: dict) -> dict:
    keyboard = []
    row = []
    for habit, done in habits_status.items():
        emoji = get_emoji(habit)
        status_symbol = "✅" if done else "❌"
        btn_text = f"{emoji} {habit.replace('_', ' ').title()}: {status_symbol}"
        callback_data = f"toggle_habit:{habit}"
        row.append({"text": btn_text, "callback_data": callback_data})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([{"text": "🏁 Concluir", "callback_data": "finish_habits"}])
    return {"inline_keyboard": keyboard}

# ─── Guided Flow Helpers ──────────────────────────────────────────────────────

def toggle_quest_text(text: str, value: bool):
    try:
        r = requests.post(f"{VAULT_SVC_URL}/api/quests/toggle-text", json={"text": text, "value": value}, timeout=5)
        if r.status_code == 200:
            print(f"[Telegram Bot] Successfully toggled quest: {text} to {value}")
    except Exception as e:
        print(f"[Telegram Bot] Error toggling quest text: {e}")

def send_work_routine_message(message_id: int = None):
    data = get_daily_tasks_data()
    tasks = data.get("work", [])
    if not tasks:
        send_message("⚠️ Não foi possível obter as tarefas de trabalho.")
        return
        
    text = "🖥️ <b>Rotina de Trabalho (SRE)</b>\n\n"
    for idx, t in enumerate(tasks):
        status = "✅" if t["done"] else "❌"
        text += f"{idx + 1}. {t['text']} - <b>{status}</b>\n"
        
    markup = get_routine_markup("work", tasks)
    if message_id:
        edit_message(message_id, text, markup)
    else:
        send_message(text, markup)

def send_domestic_routine_message(message_id: int = None):
    data = get_daily_tasks_data()
    tasks = data.get("domestic", [])
    if not tasks:
        send_message("⚠️ Não foi possível obter as tarefas domésticas.")
        return
        
    text = "🏡 <b>Rotina Doméstica</b>\n\n"
    for idx, t in enumerate(tasks):
        status = "✅" if t["done"] else "❌"
        text += f"{idx + 1}. {t['text']} - <b>{status}</b>\n"
        
    markup = get_routine_markup("domestic", tasks)
    if message_id:
        edit_message(message_id, text, markup)
    else:
        send_message(text, markup)

def send_studies_routine_message(message_id: int = None):
    data = get_daily_tasks_data()
    tasks = data.get("studies", [])
    if not tasks:
        send_message("⚠️ Não foi possível obter as tarefas de estudos.")
        return
        
    text = "📚 <b>Rotina de Estudos</b>\n\n"
    for idx, t in enumerate(tasks):
        status = "✅" if t["done"] else "❌"
        text += f"{idx + 1}. {t['text']} - <b>{status}</b>\n"
        
    markup = get_routine_markup("studies", tasks)
    if message_id:
        edit_message(message_id, text, markup)
    else:
        send_message(text, markup)

# ─── Bot Actions ──────────────────────────────────────────────────────────────

def handle_start():
    welcome_text = (
        "☸️ <b>Bem-vindo ao Lucas_OS Telegram Bot!</b>\n\n"
        "Comandos disponíveis:\n"
        "⚔️ /quests - Lista suas tarefas ativas do Obsidian.\n"
        "👤 /status - Ficha de personagem SRE, XP e streak.\n"
        "📊 /habitos - Controle de hábitos diários.\n"
        "🧹 /rotina - Inicia o checklist de tarefas domésticas.\n"
        "🖥️ /trabalho - Inicia o checklist de tarefas de trabalho SRE.\n"
        "📚 /estudos - Inicia o checklist de tarefas de estudos.\n"
        "⏰ /lembretes - Exibe as opções de rotinas e lembretes."
    )
    send_message(welcome_text)

def handle_quests():
    send_message(get_active_quests_formatted())

def handle_status():
    send_message(get_status_formatted())

def handle_habits(message_id: int = None):
    habits = get_today_habits()
    if not habits:
        markup = {
            "inline_keyboard": [
                [{"text": "💧 Iniciar Notas e Hábitos", "callback_data": "toggle_habit:agua"}]
            ]
        }
        text = "📝 Nenhuma nota diária encontrada para hoje. Deseja iniciar a nota?"
    else:
        markup = get_habits_markup(habits)
        text = "📊 <b>Controle de Hábitos de Hoje</b>\n\nSelecione os botões abaixo para marcar ou desmarcar seus hábitos diários:"
        
    if message_id:
        edit_message(message_id, text, markup)
    else:
        send_message(text, markup)

def handle_callback_query(callback_query: dict):
    qid = callback_query.get("id")
    msg = callback_query.get("message", {})
    message_id = msg.get("message_id")
    data = callback_query.get("data", "")
    
    send_telegram("answerCallbackQuery", {"callback_query_id": qid})
    
    if data.startswith("toggle_habit:"):
        habit_name = data.split(":", 1)[1]
        try:
            r = requests.post(f"{VAULT_SVC_URL}/api/habits/toggle", json={"habit": habit_name}, timeout=5)
            if r.status_code == 200:
                print(f"[Telegram Bot] Successfully toggled habit: {habit_name}")
        except Exception as e:
            print(f"[Telegram Bot] Error toggling habit: {e}")
        handle_habits(message_id)
            
    elif data == "finish_habits":
        edit_message(message_id, "🏁 <b>Controle de Hábitos Concluído!</b>\nSeus hábitos foram salvos no Obsidian.")
            
    elif data.startswith("toggle_task:"):
        parts = data.split(":")
        category = parts[1]
        idx = int(parts[2])
        
        tasks_data = get_daily_tasks_data()
        category_tasks = tasks_data.get(category, [])
        if idx < len(category_tasks):
            task = category_tasks[idx]
            new_value = not task["done"]
            toggle_quest_text(task["text"], new_value)
            
        if category == "work":
            send_work_routine_message(message_id)
        elif category == "domestic":
            send_domestic_routine_message(message_id)
        elif category == "studies":
            send_studies_routine_message(message_id)
            
    elif data.startswith("finish_routine:"):
        category = data.split(":", 1)[1]
        cat_name = "Trabalho" if category == "work" else ("Doméstica" if category == "domestic" else "Estudos")
        edit_message(message_id, f"🏁 <b>Rotina {cat_name} Concluída!</b>\nSuas atualizações foram salvas no Obsidian.")
            
    elif data == "show_quests":
        send_message(get_active_quests_formatted())
        
    elif data == "show_status":
        send_message(get_status_formatted())

# ─── Scheduler Loop ───────────────────────────────────────────────────────────

def trigger_reminder(time_slot: str):
    print(f"[Telegram Bot] Triggering scheduled reminder for: {time_slot}")
    if not CHAT_ID or not TOKEN:
        print("[Telegram Bot] Cannot send reminder: Token or Chat ID not configured.")
        return
        
    if time_slot == "09:00":
        send_work_routine_message()
    elif time_slot == "12:00":
        handle_habits()
    elif time_slot == "15:00":
        send_studies_routine_message()
    elif time_slot == "18:00":
        send_domestic_routine_message()
    elif time_slot == "21:00":
        handle_habits()

def scheduler_loop():
    last_triggered = {}
    schedule_times = ["09:00", "12:00", "15:00", "18:00", "21:00"]
    
    print("[Telegram Bot] Scheduler thread started.")
    while True:
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        today_str = now.strftime("%Y-%m-%d")
        
        if current_time in schedule_times:
            key = f"{today_str}_{current_time}"
            if last_triggered.get(key) is not True:
                trigger_reminder(current_time)
                last_triggered[key] = True
                
        time.sleep(15)

# ─── Long Polling Loop ────────────────────────────────────────────────────────

def main():
    if not TOKEN or not CHAT_ID:
        print("[Telegram Bot] CRITICAL: TELEGRAM_TOKEN and TELEGRAM_CHAT_ID are not set!")
        print("[Telegram Bot] Sleeping for 60s and retrying check...")
        while True:
            time.sleep(60)
            
    print("[Telegram Bot] Starting interactive bot daemon...")
    
    # Start Scheduler Thread
    sched_thread = threading.Thread(target=scheduler_loop, daemon=True)
    sched_thread.start()
    
    offset = 0
    while True:
        url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
        payload = {"offset": offset, "timeout": 30}
        try:
            r = requests.post(url, json=payload, timeout=35)
            if r.status_code == 200:
                data = r.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    
                    if "message" in update:
                        msg = update["message"]
                        sender_chat_id = str(msg.get("chat", {}).get("id", ""))
                        text = msg.get("text", "").strip()
                        
                        if sender_chat_id != CHAT_ID:
                            print(f"[Telegram Bot] Warning: Received unauthorized message from Chat ID: {sender_chat_id}")
                            continue
                            
                        if text == "/start" or text == "/help":
                            handle_start()
                        elif text == "/quests":
                            handle_quests()
                        elif text == "/status":
                            handle_status()
                        elif text == "/habitos":
                            handle_habits()
                        elif text == "/rotina":
                            send_domestic_routine_message()
                        elif text == "/trabalho":
                            send_work_routine_message()
                        elif text == "/estudos":
                            send_studies_routine_message()
                        elif text == "/lembretes":
                            welcome_text = (
                                "⏰ <b>Lembretes e Rotinas do Lucas_OS</b>\n\n"
                                "Escolha uma rotina para atualizar:\n"
                                "🖥️ /trabalho - Rotina de Trabalho\n"
                                "🏡 /rotina - Rotina Doméstica\n"
                                "📚 /estudos - Rotina de Estudos\n"
                                "📊 /habitos - Controle de Hábitos"
                            )
                            send_message(welcome_text)
                            
                    elif "callback_query" in update:
                        cb = update["callback_query"]
                        sender_chat_id = str(cb.get("message", {}).get("chat", {}).get("id", ""))
                        
                        if sender_chat_id != CHAT_ID:
                            continue
                            
                        handle_callback_query(cb)
                        
        except Exception as e:
            print(f"[Telegram Bot] Long poll error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
