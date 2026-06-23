import os
import time
import json
import re
import threading
from datetime import datetime
import requests

TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

TODO_SVC_URL = "http://todo-service:9005"
TODO_APP_URL = os.getenv("TODO_APP_URL", "http://192.168.0.9:9999/todo").strip()

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

def get_daily_tasks_data() -> dict:
    try:
        r = requests.get(f"{TODO_SVC_URL}/api/todo/tasks", timeout=5)
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

# ─── Guided Flow Helpers ──────────────────────────────────────────────────────

def toggle_todo_task(text: str, value: bool):
    try:
        r = requests.post(f"{TODO_SVC_URL}/api/todo/tasks/toggle", json={"text": text, "value": value}, timeout=5)
        if r.status_code == 200:
            print(f"[Telegram Bot] Successfully toggled daily task: {text} to {value}")
    except Exception as e:
        print(f"[Telegram Bot] Error toggling daily task: {e}")

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
        
    text += f"\n🔗 <a href='{TODO_APP_URL}'>Acessar Web App Todo-List</a>"
        
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
        
    text += f"\n🔗 <a href='{TODO_APP_URL}'>Acessar Web App Todo-List</a>"
        
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
        
    text += f"\n🔗 <a href='{TODO_APP_URL}'>Acessar Web App Todo-List</a>"
        
    markup = get_routine_markup("studies", tasks)
    if message_id:
        edit_message(message_id, text, markup)
    else:
        send_message(text, markup)

def send_health_routine_message(message_id: int = None):
    data = get_daily_tasks_data()
    tasks = data.get("health", [])
    if not tasks:
        send_message("⚠️ Não foi possível obter as tarefas de saúde.")
        return
        
    text = "❤️ <b>Rotina de Saúde & Bem-estar</b>\n\n"
    for idx, t in enumerate(tasks):
        status = "✅" if t["done"] else "❌"
        text += f"{idx + 1}. {t['text']} - <b>{status}</b>\n"
        
    text += f"\n🔗 <a href='{TODO_APP_URL}'>Acessar Web App Todo-List</a>"
        
    markup = get_routine_markup("health", tasks)
    if message_id:
        edit_message(message_id, text, markup)
    else:
        send_message(text, markup)

def send_finance_routine_message(message_id: int = None):
    data = get_daily_tasks_data()
    tasks = data.get("finance", [])
    if not tasks:
        send_message("⚠️ Não foi possível obter as tarefas de finanças.")
        return
        
    text = "💰 <b>Rotina de Finanças & Planejamento</b>\n\n"
    for idx, t in enumerate(tasks):
        status = "✅" if t["done"] else "❌"
        text += f"{idx + 1}. {t['text']} - <b>{status}</b>\n"
        
    text += f"\n🔗 <a href='{TODO_APP_URL}'>Acessar Web App Todo-List</a>"
        
    markup = get_routine_markup("finance", tasks)
    if message_id:
        edit_message(message_id, text, markup)
    else:
        send_message(text, markup)

def send_general_summary_message(is_final: bool = False):
    data = get_daily_tasks_data()
    if not data:
        send_message("⚠️ Não foi possível obter o resumo de tarefas de hoje.")
        return
        
    title = "🌃 <b>Fechamento do Dia - Lucas_OS</b>" if is_final else "☀️ <b>Check-in do Dia - Lucas_OS</b>"
    text = f"{title}\n\n"
    
    categories = {
        "work": "🖥️ Trabalho SRE",
        "domestic": "🏡 Rotina Doméstica",
        "studies": "📚 Estudos & Labs",
        "health": "❤️ Saúde & Bem-estar",
        "finance": "💰 Finanças & Planejamento"
    }
    
    total_tasks = 0
    done_tasks = 0
    
    for cat_key, cat_name in categories.items():
        tasks = data.get(cat_key, [])
        if tasks:
            text += f"<b>{cat_name}:</b>\n"
            for t in tasks:
                total_tasks += 1
                status = "❌"
                if t["done"]:
                    done_tasks += 1
                    status = "✅"
                text += f" {status} {t['text']}\n"
            text += "\n"
            
    if total_tasks > 0:
        pct = int((done_tasks / total_tasks) * 100)
        text += f"📊 Progresso Geral: <b>{pct}%</b> ({done_tasks}/{total_tasks} concluídas)\n"
    else:
        text += "📝 Nenhuma tarefa cadastrada para hoje.\n"
        
    text += f"\n🔗 <a href='{TODO_APP_URL}'>Acessar Web App Todo-List</a>"
    
    markup = {
        "inline_keyboard": [
            [{"text": "🔗 Abrir Web App", "url": TODO_APP_URL}]
        ]
    }
    
    send_message(text, markup)

# ─── Bot Actions ──────────────────────────────────────────────────────────────

def handle_start():
    welcome_text = (
        "☸️ <b>Bem-vindo ao Lucas_OS Telegram Bot!</b>\n\n"
        "Comandos disponíveis:\n"
        "🧹 /rotina - Inicia o checklist de tarefas domésticas.\n"
        "🖥️ /trabalho - Inicia o checklist de tarefas de trabalho SRE.\n"
        "📚 /estudos - Inicia o checklist de tarefas de estudos.\n"
        "❤️ /saude - Inicia o checklist de tarefas de saúde.\n"
        "💰 /financas - Inicia o checklist de tarefas de finanças.\n"
        "📊 /resumo - Exibe o progresso geral e resumo de tarefas de hoje.\n"
        "⏰ /lembretes - Exibe as opções de rotinas e lembretes."
    )
    send_message(welcome_text)

def handle_callback_query(callback_query: dict):
    qid = callback_query.get("id")
    msg = callback_query.get("message", {})
    message_id = msg.get("message_id")
    data = callback_query.get("data", "")
    
    send_telegram("answerCallbackQuery", {"callback_query_id": qid})
    
    if data.startswith("toggle_task:"):
        parts = data.split(":")
        category = parts[1]
        idx = int(parts[2])
        
        tasks_data = get_daily_tasks_data()
        category_tasks = tasks_data.get(category, [])
        if idx < len(category_tasks):
            task = category_tasks[idx]
            new_value = not task["done"]
            toggle_todo_task(task["text"], new_value)
            
        if category == "work":
            send_work_routine_message(message_id)
        elif category == "domestic":
            send_domestic_routine_message(message_id)
        elif category == "studies":
            send_studies_routine_message(message_id)
        elif category == "health":
            send_health_routine_message(message_id)
        elif category == "finance":
            send_finance_routine_message(message_id)
            
    elif data.startswith("finish_routine:"):
        category = data.split(":", 1)[1]
        cat_name = "Trabalho" if category == "work" else ("Doméstica" if category == "domestic" else ("Estudos" if category == "studies" else ("Saúde" if category == "health" else "Finanças")))
        edit_message(message_id, f"🏁 <b>Rotina {cat_name} Concluída!</b>\nSuas atualizações foram salvas no Banco de Dados.")

# ─── Scheduler Loop ───────────────────────────────────────────────────────────

def trigger_reminder(time_slot: str):
    print(f"[Telegram Bot] Triggering scheduled reminder for: {time_slot}")
    if not CHAT_ID or not TOKEN:
        print("[Telegram Bot] Cannot send reminder: Token or Chat ID not configured.")
        return
        
    if time_slot == "06:00":
        send_domestic_routine_message()
    elif time_slot == "09:00":
        send_work_routine_message()
    elif time_slot == "12:00":
        send_general_summary_message(is_final=False)
    elif time_slot == "15:00":
        send_studies_routine_message()
    elif time_slot == "18:00":
        send_domestic_routine_message()
    elif time_slot == "21:00":
        send_general_summary_message(is_final=True)

def scheduler_loop():
    last_triggered = {}
    schedule_times = ["06:00", "09:00", "12:00", "15:00", "18:00", "21:00"]
    
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
                        elif text == "/rotina":
                            send_domestic_routine_message()
                        elif text == "/trabalho":
                            send_work_routine_message()
                        elif text == "/estudos":
                            send_studies_routine_message()
                        elif text == "/saude":
                            send_health_routine_message()
                        elif text == "/financas":
                            send_finance_routine_message()
                        elif text == "/resumo":
                            send_general_summary_message(is_final=False)
                        elif text == "/lembretes":
                            welcome_text = (
                                "⏰ <b>Lembretes e Rotinas do Lucas_OS</b>\n\n"
                                "Escolha uma rotina ou resumo para atualizar:\n"
                                "🖥️ /trabalho - Rotina de Trabalho\n"
                                "🏡 /rotina - Rotina Doméstica\n"
                                "📚 /estudos - Rotina de Estudos\n"
                                "❤️ /saude - Rotina de Saúde\n"
                                "💰 /financas - Rotina de Finanças\n"
                                "📊 /resumo - Resumo Geral de Hoje"
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
