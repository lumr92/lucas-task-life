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

def get_habits_markup(habits_status: dict) -> dict:
    keyboard = []
    for habit, done in habits_status.items():
        emoji = get_emoji(habit)
        status_symbol = "✅" if done else "❌"
        btn_text = f"{emoji} {habit.replace('_', ' ').title()}: {status_symbol}"
        callback_data = f"toggle_habit:{habit}"
        keyboard.append([{"text": btn_text, "callback_data": callback_data}])
    
    # Add a refresh button at the bottom
    keyboard.append([{"text": "🔄 Atualizar Status", "callback_data": "refresh_habits"}])
    return {"inline_keyboard": keyboard}

# ─── Guided Flow Helpers ──────────────────────────────────────────────────────

def toggle_quest_text(text: str, value: bool):
    try:
        r = requests.post(f"{VAULT_SVC_URL}/api/quests/toggle-text", json={"text": text, "value": value}, timeout=5)
        if r.status_code == 200:
            print(f"[Telegram Bot] Successfully toggled quest: {text} to {value}")
    except Exception as e:
        print(f"[Telegram Bot] Error toggling quest text: {e}")

def send_step_message(step: int, message_id: int = None):
    if step == 1:
        text = "🐱 <b>[Passo 1/4] Rotina Doméstica</b>\nVocê limpou a caixa de areia dos gatos hoje?"
        markup = {
            "inline_keyboard": [
                [
                    {"text": "✅ Sim, limpei", "callback_data": "flow:1:yes"},
                    {"text": "⏭️ Pular", "callback_data": "flow:1:skip"}
                ]
            ]
        }
    elif step == 2:
        text = "💧 <b>[Passo 2/4] Rotina Doméstica</b>\nVocê trocou a água das meninas?"
        markup = {
            "inline_keyboard": [
                [
                    {"text": "✅ Sim, troquei", "callback_data": "flow:2:yes"},
                    {"text": "⏭️ Pular", "callback_data": "flow:2:skip"}
                ]
            ]
        }
    elif step == 3:
        text = "👕 <b>[Passo 3/4] Rotina Doméstica</b>\nTem roupa para guardar hoje?"
        markup = {
            "inline_keyboard": [
                [
                    {"text": "🟢 Sim", "callback_data": "flow:3:yes"},
                    {"text": "🔴 Não", "callback_data": "flow:3:no"}
                ]
            ]
        }
    elif step == 4:
        text = "👕 <b>[Passo 4/4] Rotina Doméstica</b>\nVocê já guardou as roupas?"
        markup = {
            "inline_keyboard": [
                [
                    {"text": "✅ Sim, guardei", "callback_data": "flow:4:yes"},
                    {"text": "❌ Ainda não", "callback_data": "flow:4:no"}
                ]
            ]
        }
    else:
        text = "🏁 <b>Rotina Diária Concluída!</b>\nTodas as tarefas respondidas foram devidamente atualizadas no seu Obsidian. Bom trabalho, Lucas! ☸️"
        markup = None
        
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
        "💧 /habitos - Painel interativo para registrar hábitos.\n"
        "🧹 /rotina - Inicia o checklist de tarefas domésticas."
    )
    send_message(welcome_text)

def handle_quests():
    send_message(get_active_quests_formatted())

def handle_status():
    send_message(get_status_formatted())

def handle_habits():
    habits = get_today_habits()
    if not habits:
        send_message("📝 Nenhuma nota diária encontrada para hoje. Deseja iniciar clicando em qualquer hábito?", {
            "inline_keyboard": [
                [{"text": "💧 Iniciar Notas e Hábitos", "callback_data": "toggle_habit:agua"}]
            ]
        })
        return
    
    markup = get_habits_markup(habits)
    send_message("💧 <b>Painel de Hábitos de Hoje</b>\nSelecione os botões abaixo para marcar/desmarcar:", markup)

def handle_callback_query(callback_query: dict):
    qid = callback_query.get("id")
    msg = callback_query.get("message", {})
    message_id = msg.get("message_id")
    data = callback_query.get("data", "")
    
    # Ack callback query to stop loading spinner
    send_telegram("answerCallbackQuery", {"callback_query_id": qid})
    
    if data.startswith("toggle_habit:"):
        habit_name = data.split(":", 1)[1]
        # Call toggle API
        try:
            r = requests.post(f"{VAULT_SVC_URL}/api/habits/toggle", json={"habit": habit_name}, timeout=5)
            if r.status_code == 200:
                print(f"[Telegram Bot] Successfully toggled habit: {habit_name}")
        except Exception as e:
            print(f"[Telegram Bot] Error toggling habit: {e}")
        
        # Re-render habits menu
        habits = get_today_habits()
        if habits:
            edit_message(message_id, "💧 <b>Painel de Hábitos de Hoje</b>\nSelecione os botões abaixo para marcar/desmarcar:", get_habits_markup(habits))
            
    elif data == "refresh_habits":
        habits = get_today_habits()
        if habits:
            edit_message(message_id, "💧 <b>Painel de Hábitos de Hoje (Atualizado)</b>\nSelecione os botões abaixo para marcar/desmarcar:", get_habits_markup(habits))
            
    elif data.startswith("flow:"):
        parts = data.split(":")
        step = int(parts[1])
        action = parts[2]
        
        if step == 1:
            if action == "yes":
                toggle_quest_text("Limpar caixas de areia dos gatos", True)
            send_step_message(2, message_id)
        elif step == 2:
            if action == "yes":
                toggle_quest_text("Trocar água das meninas", True)
            send_step_message(3, message_id)
        elif step == 3:
            if action == "yes":
                send_step_message(4, message_id)
            else:
                toggle_quest_text("Guardar roupas", False)
                send_step_message(5, message_id)
        elif step == 4:
            if action == "yes":
                toggle_quest_text("Guardar roupas", True)
            else:
                toggle_quest_text("Guardar roupas", False)
            send_step_message(5, message_id)

# ─── Scheduler Loop ───────────────────────────────────────────────────────────

def trigger_reminder(time_slot: str):
    print(f"[Telegram Bot] Triggering scheduled reminder for: {time_slot}")
    if not CHAT_ID or not TOKEN:
        print("[Telegram Bot] Cannot send reminder: Token or Chat ID not configured.")
        return
        
    if time_slot == "09:00":
        text = "☸️ <b>Bom dia, Lucas!</b>\nComeçando as atividades diárias. Aqui estão suas tarefas:\n\n" + get_active_quests_formatted()
        send_message(text)
    elif time_slot == "12:00":
        send_message("🕛 <b>Checkpoint das 12h:</b>\nComo está o progresso? Não se esqueça de manter a hidratação e registrar seus hábitos no Obsidian! /habitos")
    elif time_slot == "15:00":
        send_message("🕒 <b>Checkpoint das 15h:</b>\nQue tal um café e 5 minutos de alongamento? Dê uma olhada nas suas quests pendentes hoje com o comando /quests")
    elif time_slot == "18:00":
        # Dispara automaticamente o fluxo de tarefas domésticas
        send_step_message(1)
    elif time_slot == "21:00":
        # Dispara automaticamente o painel de hábitos interativos do dia
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
                    
                    # Check messages
                    if "message" in update:
                        msg = update["message"]
                        sender_chat_id = str(msg.get("chat", {}).get("id", ""))
                        text = msg.get("text", "").strip()
                        
                        # Only reply to the configured Chat ID
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
                            send_step_message(1)
                            
                    # Check callback queries (buttons clicked)
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
