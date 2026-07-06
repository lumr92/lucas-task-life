import os
import time
import json
import re
from datetime import datetime
from typing import Optional, Dict, List, Any
import requests

TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
FINANCE_SVC_URL = "http://finance-service:9006"

def get_finance_summary_data(month_str: str) -> dict:
    try:
        r = requests.get(f"{FINANCE_SVC_URL}/api/finance/summary?month={month_str}", timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[Telegram Bot] Error fetching finance summary: {e}")
    return {}

def format_currency_brl(val: float) -> str:
    return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def send_finance_summary_telegram():
    today_str = datetime.now().strftime("%Y-%m")
    summary = get_finance_summary_data(today_str)
    if not summary:
        send_message("⚠️ Não foi possível obter o resumo financeiro de hoje.")
        return
        
    text = (
        f"💰 <b>Painel Financeiro - Lucas_OS</b>\n"
        f"Referência: <b>{today_str}</b>\n\n"
        f"🏛️ Saldo em Contas: <b>{format_currency_brl(summary.get('total_accounts_balance', 0.0))}</b>\n"
        f"💳 Faturas de Cartão: <b>{format_currency_brl(summary.get('total_cards_outstanding', 0.0))}</b>\n"
        f"📊 Patrimônio Líquido: <b>{format_currency_brl(summary.get('net_worth', 0.0))}</b>\n\n"
        f"📈 Receitas no Mês: <b>{format_currency_brl(summary.get('monthly_income', 0.0))}</b>\n"
        f"📉 Despesas no Mês: <b>{format_currency_brl(summary.get('monthly_expenses', 0.0))}</b>\n"
        f"⚖️ Saldo Líquido Mensal: <b>{format_currency_brl(summary.get('net_monthly_savings', 0.0))}</b>\n"
    )
    
    breakdown = summary.get("category_breakdown", {})
    if breakdown:
        text += "\n<b>Despesas por Categoria:</b>\n"
        sorted_breakdown = sorted(breakdown.items(), key=lambda x: x[1], reverse=True)
        for cat, val in sorted_breakdown:
            text += f" • {cat}: {format_currency_brl(val)}\n"
            
    finance_web_url = os.getenv("FINANCE_APP_URL", "http://192.168.0.9:9999/finance").strip()
    text += f"\n🔗 <a href='{finance_web_url}'>Acessar Web App Financeiro</a>"
    
    markup = {
        "inline_keyboard": [
            [{"text": "🔗 Abrir Web App Financeiro", "url": finance_web_url}]
        ]
    }
    send_message(text, markup)

def resolve_account_or_card(name: str) -> Optional[dict]:
    try:
        r = requests.get(f"{FINANCE_SVC_URL}/api/finance/accounts", timeout=3)
        if r.status_code == 200:
            for acc in r.json():
                if name.lower() in acc["name"].lower():
                    return {"type": "account", "id": acc["id"], "name": acc["name"]}
    except Exception as e:
        print(f"Error resolving account: {e}")
        
    try:
        r = requests.get(f"{FINANCE_SVC_URL}/api/finance/cards", timeout=3)
        if r.status_code == 200:
            for card in r.json():
                if name.lower() in card["name"].lower():
                    return {"type": "card", "id": card["id"], "name": card["name"]}
    except Exception as e:
        print(f"Error resolving card: {e}")
        
    return None

def handle_quick_gasto(text: str):
    parts = text.split(maxsplit=4)
    if len(parts) < 5:
        help_text = (
            "⚠️ <b>Uso incorreto do comando /gasto</b>\n\n"
            "Formato correto:\n"
            "<code>/gasto &lt;valor&gt; &lt;categoria&gt; &lt;conta/cartão&gt; &lt;descrição&gt;</code>\n\n"
            "Exemplos:\n"
            "• <code>/gasto 35.50 Alimentação Nubank Almoço</code>\n"
            "• <code>/gasto 120.00 Lazer Cartao_Nubank Cinema</code>"
        )
        send_message(help_text)
        return
        
    val_str = parts[1].replace(",", ".")
    category = parts[2]
    source_name = parts[3].replace("_", " ")
    description = parts[4]
    
    try:
        amount = float(val_str)
    except ValueError:
        send_message(f"⚠️ Valor inválido: '<b>{val_str}</b>'. Use números decimais separados por ponto ou vírgula.")
        return
        
    resolved = resolve_account_or_card(source_name)
    if not resolved:
        send_message(f"⚠️ Não encontrei conta ou cartão correspondente a '<b>{source_name}</b>'.")
        return
        
    payload = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "description": description,
        "amount": -abs(amount),
        "category": category,
    }
    
    if resolved["type"] == "account":
        payload["account_id"] = resolved["id"]
        source_label = f"🏛️ Conta {resolved['name']}"
    else:
        payload["credit_card_id"] = resolved["id"]
        source_label = f"💳 Cartão {resolved['name']}"
        
    try:
        r = requests.post(f"{FINANCE_SVC_URL}/api/finance/transactions", json=payload, timeout=5)
        if r.status_code == 200:
            send_message(
                f"✅ <b>Despesa registrada com sucesso!</b>\n\n"
                f"📝 Descrição: {description}\n"
                f"🏷️ Categoria: {category}\n"
                f"💰 Valor: <b>{format_currency_brl(amount)}</b>\n"
                f"💳 Destino/Origem: {source_label}"
            )
        else:
            err = r.json().get("detail", "Erro desconhecido")
            send_message(f"⚠️ Erro ao salvar transação: {err}")
    except Exception as e:
        send_message(f"⚠️ Erro ao conectar ao finance-service: {e}")

def handle_quick_receita(text: str):
    parts = text.split(maxsplit=4)
    if len(parts) < 5:
        help_text = (
            "⚠️ <b>Uso incorreto do comando /receita</b>\n\n"
            "Formato correto (apenas para contas correntes):\n"
            "<code>/receita &lt;valor&gt; &lt;categoria&gt; &lt;conta&gt; &lt;descrição&gt;</code>\n\n"
            "Exemplo:\n"
            "• <code>/receita 2500.00 Salário Nubank Salário Mensal</code>"
        )
        send_message(help_text)
        return
        
    val_str = parts[1].replace(",", ".")
    category = parts[2]
    source_name = parts[3].replace("_", " ")
    description = parts[4]
    
    try:
        amount = float(val_str)
    except ValueError:
        send_message(f"⚠️ Valor inválido: '<b>{val_str}</b>'.")
        return
        
    resolved = resolve_account_or_card(source_name)
    if not resolved or resolved["type"] != "account":
        send_message(f"⚠️ Não encontrei conta corrente correspondente a '<b>{source_name}</b>'. Receitas não podem ser associadas a cartões.")
        return
        
    payload = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "description": description,
        "amount": abs(amount),
        "category": category,
        "account_id": resolved["id"]
    }
    
    try:
        r = requests.post(f"{FINANCE_SVC_URL}/api/finance/transactions", json=payload, timeout=5)
        if r.status_code == 200:
            send_message(
                f"✅ <b>Receita registrada com sucesso!</b>\n\n"
                f"📝 Descrição: {description}\n"
                f"🏷️ Categoria: {category}\n"
                f"💰 Valor: <b>{format_currency_brl(amount)}</b>\n"
                f"🏛️ Conta: {resolved['name']}"
            )
        else:
            err = r.json().get("detail", "Erro desconhecido")
            send_message(f"⚠️ Erro ao salvar transação: {err}")
    except Exception as e:
        send_message(f"⚠️ Erro ao conectar ao finance-service: {e}")

def handle_quick_transferencia(text: str):
    parts = text.split(maxsplit=4)
    if len(parts) < 5:
        help_text = (
            "⚠️ <b>Uso incorreto do comando /transferencia</b>\n\n"
            "Formato correto:\n"
            "<code>/transferencia &lt;valor&gt; &lt;origem&gt; &lt;destino&gt; &lt;descrição&gt;</code>\n\n"
            "Exemplos:\n"
            "• <code>/transferencia 100 Nubank Poupança Guardar</code>\n"
            "• <code>/transferencia 693.96 Nubank Cartao_Nubank Pagar fatura</code>"
        )
        send_message(help_text)
        return
        
    val_str = parts[1].replace(",", ".")
    src_name = parts[2].replace("_", " ")
    dest_name = parts[3].replace("_", " ")
    description = parts[4]
    
    try:
        amount = float(val_str)
    except ValueError:
        send_message(f"⚠️ Valor inválido: '<b>{val_str}</b>'.")
        return
        
    src_resolved = resolve_account_or_card(src_name)
    if not src_resolved or src_resolved["type"] != "account":
        send_message(f"⚠️ Conta de origem '<b>{src_name}</b>' inválida. Transferências devem originar de contas correntes/dinheiro.")
        return
        
    dest_resolved = resolve_account_or_card(dest_name)
    if not dest_resolved:
        send_message(f"⚠️ Não encontrei conta ou cartão de destino que combine com '<b>{dest_name}</b>'.")
        return
        
    payload = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "description": description,
        "amount": amount,
        "category": "Outros",
        "account_id": src_resolved["id"],
        "is_transfer": True
    }
    
    if dest_resolved["type"] == "account":
        payload["destination_account_id"] = dest_resolved["id"]
        dest_label = f"🏛️ Conta {dest_resolved['name']}"
    else:
        payload["credit_card_id"] = dest_resolved["id"]
        dest_label = f"💳 Fatura Cartão {dest_resolved['name']}"
        
    try:
        r = requests.post(f"{FINANCE_SVC_URL}/api/finance/transactions", json=payload, timeout=5)
        if r.status_code == 200:
            send_message(
                f"✅ <b>Transferência registrada com sucesso!</b>\n\n"
                f"📝 Descrição: {description}\n"
                f"💰 Valor: <b>{format_currency_brl(abs(amount))}</b>\n"
                f"🏛️ Origem: Conta {src_resolved['name']}\n"
                f"🏁 Destino: {dest_label}"
            )
        else:
            err = r.json().get("detail", "Erro desconhecido")
            send_message(f"⚠️ Erro ao registrar no backend: {err}")
    except Exception as e:
        send_message(f"⚠️ Erro ao conectar ao finance-service: {e}")

def parse_and_register_notification(text: str) -> bool:
    text_lower = text.lower()
    account_id = None
    account_name = ""
    
    if "bb " in text_lower or "banco do brasil" in text_lower or "bb:" in text_lower or text_lower.startswith("bb"):
        account_id = 4
        account_name = "BB"
    elif "mercado pago" in text_lower or "mercadopago" in text_lower:
        account_id = 5
        account_name = "Mercado Pago"
    else:
        if any(kw in text_lower for kw in ["pix", "enviou", "recebeu", "transferência", "saída", "entrada"]):
            account_id = 4
            account_name = "BB"
        else:
            return False

    is_outflow = True
    if any(kw in text_lower for kw in ["entrada", "recebido", "recebeu", "credito", "recebimento"]):
        is_outflow = False

    match = re.search(r'([0-9\.]+),[0-9]{2}', text)
    if not match:
        return False
        
    amount_str = match.group(0).replace('.', '').replace(',', '.')
    try:
        amount = float(amount_str)
    except ValueError:
        return False
        
    if is_outflow:
        amount = -abs(amount)
    else:
        amount = abs(amount)

    payload = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "description": text,
        "amount": amount,
        "category": "Outros",
        "account_id": account_id
    }
    
    try:
        r = requests.post(f"{FINANCE_SVC_URL}/api/finance/transactions", json=payload, timeout=5)
        if r.status_code in [200, 201]:
            direction_label = "Despesa" if amount < 0 else "Receita"
            val_formatted = format_currency_brl(abs(amount))
            send_message(
                f"✅ <b>Lançamento Automático Realizado!</b>\n\n"
                f"🏛️ Conta: <b>{account_name}</b>\n"
                f"🏷️ Tipo: <b>{direction_label}</b>\n"
                f"💰 Valor: <b>{val_formatted}</b>\n"
                f"📝 Descrição: <i>{text}</i>"
            )
            return True
        else:
            err_msg = r.json().get("detail", "Erro desconhecido") if r.status_code == 400 else r.text
            send_message(f"⚠️ Erro ao registrar transação: {err_msg}")
            return True
    except Exception as e:
        send_message(f"⚠️ Erro de conexão ao salvar transação: {e}")
        return True

    return False

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

def handle_start():
    welcome_text = (
        "☸️ <b>Lucas_OS - Controle Financeiro</b>\n\n"
        "Comandos Disponíveis:\n"
        "💰 /financeiro ou /saldo - Exibe saldos, faturas e patrimônio líquido.\n"
        "📥 /receita [valor] [categoria] [conta] [descrição] - Registra ganhos.\n"
        "📤 /gasto [valor] [categoria] [origem] [descrição] - Registra despesas.\n"
        "🔄 /transferencia [valor] [origem] [destino] [descrição] - Transferências e Faturas.\n\n"
        "💡 <i>Você também pode colar notificações de Pix/SMS diretamente aqui para registro automático!</i>"
    )
    send_message(welcome_text)

def main():
    if not TOKEN or not CHAT_ID:
        print("[Telegram Bot] CRITICAL: TELEGRAM_TOKEN and TELEGRAM_CHAT_ID are not set!")
        while True:
            time.sleep(60)
            
    print("[Telegram Bot] Starting interactive bot daemon...")
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
                            continue
                            
                        if text == "/start" or text == "/help":
                            handle_start()
                        elif text == "/financeiro" or text == "/saldo":
                            send_finance_summary_telegram()
                        elif text.startswith("/gasto"):
                            handle_quick_gasto(text)
                        elif text.startswith("/receita"):
                            handle_quick_receita(text)
                        elif text.startswith("/transferencia"):
                            handle_quick_transferencia(text)
                        elif text.startswith("/"):
                            send_message("⚠️ Comando não reconhecido. Use /help para ver os comandos disponíveis.")
                        elif text:
                            is_parsed = parse_and_register_notification(text)
                            if not is_parsed:
                                send_message(
                                    "⚠️ <b>Mensagem não interpretada como transação</b>\n\n"
                                    "Para registrar despesas/receitas rápidas via texto, envie uma notificação de banco contendo valores (ex: <i>'BB Saída: Pix de R$ 10,00...'</i>) ou use os comandos:\n"
                                    "• <code>/gasto &lt;valor&gt; &lt;categoria&gt; &lt;conta&gt; &lt;descrição&gt;</code>"
                                )
        except Exception as e:
            print(f"[Telegram Bot] Long poll error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
