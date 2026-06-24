import os
import time
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, date
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import HTMLResponse

app = FastAPI(title="Lucas_OS Finance Service", version="1.0.0")

# Database configuration from environment variables
DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "lucas_todo")
DB_USER = os.getenv("POSTGRES_USER", "lucas_user")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "lucas_password")

def get_db_connection():
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
            print(f"[Finance Service] Database connection failed. Retrying... ({retries} left). Error: {e}")
            time.sleep(2)
    raise Exception("Could not connect to the database after several retries.")

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Accounts Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            type VARCHAR(20) NOT NULL, -- 'checking', 'savings', 'investment', 'cash'
            initial_balance DECIMAL(12, 2) DEFAULT 0.00,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # 2. Credit Cards Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS credit_cards (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            credit_limit DECIMAL(12, 2) NOT NULL,
            closing_day INTEGER NOT NULL CHECK (closing_day >= 1 AND closing_day <= 31),
            due_day INTEGER NOT NULL CHECK (due_day >= 1 AND due_day <= 31),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # 3. Financial Records (Transactions) Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS financial_records (
            id SERIAL PRIMARY KEY,
            date DATE NOT NULL,
            description VARCHAR(255) NOT NULL,
            amount DECIMAL(12, 2) NOT NULL, -- positive for income, negative for expense
            category VARCHAR(50) NOT NULL,
            account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
            credit_card_id INTEGER REFERENCES credit_cards(id) ON DELETE SET NULL,
            is_transfer BOOLEAN DEFAULT FALSE,
            destination_account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    
    # Seed default accounts if empty
    cursor.execute("SELECT COUNT(*) FROM accounts")
    acc_count = cursor.fetchone()[0]
    if acc_count == 0:
        cursor.execute("INSERT INTO accounts (name, type, initial_balance) VALUES ('Carteira (Dinheiro)', 'cash', 0.00)")
        cursor.execute("INSERT INTO accounts (name, type, initial_balance) VALUES ('Nubank Corrente', 'checking', 0.00)")
        cursor.execute("INSERT INTO accounts (name, type, initial_balance) VALUES ('Poupança', 'savings', 0.00)")
        conn.commit()
        
    # Seed default credit cards if empty
    cursor.execute("SELECT COUNT(*) FROM credit_cards")
    card_count = cursor.fetchone()[0]
    if card_count == 0:
        cursor.execute("INSERT INTO credit_cards (name, credit_limit, closing_day, due_day) VALUES ('Cartão Nubank', 3000.00, 10, 15)")
        conn.commit()
        
    cursor.close()
    conn.close()
    print("[Finance Service] Database initialized successfully.")

# Run database setup on startup
try:
    init_db()
except Exception as err:
    print(f"[Finance Service] Startup database initialization error: {err}")

# ─── Helper Functions ─────────────────────────────────────────────────────────

def get_billing_cycle(transaction_date: date, closing_day: int) -> str:
    """Calculates the billing cycle month (YYYY-MM) for a credit card transaction."""
    if transaction_date.day > closing_day:
        # Transaction falls into the next invoice cycle
        if transaction_date.month == 12:
            cycle_date = date(transaction_date.year + 1, 1, 1)
        else:
            cycle_date = date(transaction_date.year, transaction_date.month + 1, 1)
    else:
        cycle_date = transaction_date
    return cycle_date.strftime("%Y-%m")

# ─── API Endpoints ────────────────────────────────────────────────────────────

@app.get("/finance", response_class=HTMLResponse)
def get_finance_page():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "finance.html")
    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail="Template file finance.html not found.")
    with open(template_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content, status_code=200)

# ─── Accounts API ─────────────────────────────────────────────────────────────

@app.get("/api/finance/accounts")
def get_accounts():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Query accounts and calculate their current balances dynamically
        # Balance = initial_balance + sum(amount in records where account_id = a.id) + sum(abs(amount) in records where destination_account_id = a.id and is_transfer = True)
        cursor.execute("""
            SELECT 
                a.id, 
                a.name, 
                a.type, 
                CAST(a.initial_balance AS DOUBLE PRECISION) as initial_balance,
                CAST(
                    a.initial_balance + 
                    COALESCE((SELECT SUM(amount) FROM financial_records WHERE account_id = a.id), 0) +
                    COALESCE((SELECT SUM(ABS(amount)) FROM financial_records WHERE destination_account_id = a.id AND is_transfer = TRUE), 0)
                AS DOUBLE PRECISION) as current_balance
            FROM accounts a
            ORDER BY a.name ASC
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except Exception as e:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/finance/accounts")
def add_account(payload: Dict[str, Any] = Body(...)):
    name = payload.get("name")
    type_ = payload.get("type", "checking")
    initial_balance = payload.get("initial_balance", 0.00)
    
    if not name:
        raise HTTPException(status_code=400, detail="Missing account name")
    if type_ not in ["checking", "savings", "investment", "cash"]:
        raise HTTPException(status_code=400, detail="Invalid account type")
        
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            "INSERT INTO accounts (name, type, initial_balance) VALUES (%s, %s, %s) "
            "ON CONFLICT (name) DO UPDATE SET type=EXCLUDED.type, initial_balance=EXCLUDED.initial_balance RETURNING id, name, type, initial_balance",
            (name, type_, initial_balance)
        )
        new_acc = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "success", "account": new_acc}
    except Exception as e:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

# ─── Credit Cards API ─────────────────────────────────────────────────────────

@app.get("/api/finance/cards")
def get_cards(cycle: Optional[str] = None):
    """Lists all credit cards. Calculates outstanding balances and the invoice total for a target cycle (YYYY-MM)."""
    if not cycle:
        cycle = date.today().strftime("%Y-%m")
        
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Get all cards
        cursor.execute("SELECT id, name, CAST(credit_limit AS DOUBLE PRECISION) as credit_limit, closing_day, due_day FROM credit_cards ORDER BY name ASC")
        cards = cursor.fetchall()
        
        # For each card, calculate outstanding balance (all time) and the specific cycle invoice
        for card in cards:
            card_id = card["id"]
            closing_day = card["closing_day"]
            
            # Fetch all card transactions (purchases + payments)
            cursor.execute("SELECT amount, date, is_transfer FROM financial_records WHERE credit_card_id = %s", (card_id,))
            records = cursor.fetchall()
            
            outstanding_balance = 0.0
            cycle_invoice_total = 0.0
            
            for r in records:
                amount = float(r["amount"])
                t_date = r["date"]
                is_transfer = r["is_transfer"]
                
                # All time outstanding
                # Purchases are negative, payments are transfers which are also negative but we treat them as adding back to limit
                if is_transfer:
                    outstanding_balance -= abs(amount) # reduces what we owe
                else:
                    outstanding_balance += abs(amount) # increases what we owe
                
                # Calculate billing cycle
                t_cycle = get_billing_cycle(t_date, closing_day)
                if t_cycle == cycle:
                    if is_transfer:
                        cycle_invoice_total -= abs(amount)
                    else:
                        cycle_invoice_total += abs(amount)
                        
            card["outstanding_balance"] = outstanding_balance
            card["available_limit"] = max(0.0, card["credit_limit"] - outstanding_balance)
            card["cycle_invoice_total"] = cycle_invoice_total
            card["target_cycle"] = cycle
            
        cursor.close()
        conn.close()
        return cards
    except Exception as e:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/finance/cards")
def add_card(payload: Dict[str, Any] = Body(...)):
    name = payload.get("name")
    credit_limit = payload.get("credit_limit")
    closing_day = payload.get("closing_day")
    due_day = payload.get("due_day")
    
    if not name or credit_limit is None or closing_day is None or due_day is None:
        raise HTTPException(status_code=400, detail="Missing required card parameters")
        
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            "INSERT INTO credit_cards (name, credit_limit, closing_day, due_day) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (name) DO UPDATE SET credit_limit=EXCLUDED.credit_limit, closing_day=EXCLUDED.closing_day, due_day=EXCLUDED.due_day RETURNING id, name, credit_limit, closing_day, due_day",
            (name, credit_limit, closing_day, due_day)
        )
        new_card = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "success", "card": new_card}
    except Exception as e:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

# ─── Transactions API ─────────────────────────────────────────────────────────

@app.get("/api/finance/transactions")
def get_transactions(month: Optional[str] = None, account_id: Optional[int] = None, credit_card_id: Optional[int] = None):
    """Fetches transactions, optional filters by month (YYYY-MM), account_id, or credit_card_id."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        query = """
            SELECT 
                r.id, 
                TO_CHAR(r.date, 'YYYY-MM-DD') as date, 
                r.description, 
                CAST(r.amount AS DOUBLE PRECISION) as amount, 
                r.category,
                r.account_id,
                a.name as account_name,
                r.credit_card_id,
                c.name as credit_card_name,
                r.is_transfer,
                r.destination_account_id,
                dest.name as destination_account_name
            FROM financial_records r
            LEFT JOIN accounts a ON r.account_id = a.id
            LEFT JOIN credit_cards c ON r.credit_card_id = c.id
            LEFT JOIN accounts dest ON r.destination_account_id = dest.id
            WHERE 1=1
        """
        params = []
        
        if month:
            # Match date of transaction OR if it's a credit card transaction, match its cycle!
            # Since credit card invoice dates can cross calendar months, we can filter in python or do simple month query.
            # To keep it simple, we filter standard transactions by calendar month, and card transactions by their cycle!
            pass # We will do the filtering in Python for precision and simplicity
            
        if account_id:
            query += " AND (r.account_id = %s OR r.destination_account_id = %s)"
            params.extend([account_id, account_id])
            
        if credit_card_id:
            query += " AND r.credit_card_id = %s"
            params.append(credit_card_id)
            
        query += " ORDER BY r.date DESC, r.id DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # If month filter (YYYY-MM) is active, filter them dynamically
        if month:
            filtered_rows = []
            for r in rows:
                t_date = datetime.strptime(r["date"], "%Y-%m-%d").date()
                if r["credit_card_id"]:
                    # Fetch card closing day
                    cursor.execute("SELECT closing_day FROM credit_cards WHERE id = %s", (r["credit_card_id"],))
                    card_row = cursor.fetchone()
                    closing_day = card_row["closing_day"] if card_row else 10
                    cycle = get_billing_cycle(t_date, closing_day)
                    if cycle == month:
                        filtered_rows.append(r)
                else:
                    # Standard transaction calendar month match
                    if t_date.strftime("%Y-%m") == month:
                        filtered_rows.append(r)
            rows = filtered_rows
            
        cursor.close()
        conn.close()
        return rows
    except Exception as e:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/finance/transactions")
def add_transaction(payload: Dict[str, Any] = Body(...)):
    date_str = payload.get("date")
    description = payload.get("description")
    amount = payload.get("amount") # Float, positive for income, negative for expense
    category = payload.get("category", "Outros")
    account_id = payload.get("account_id")
    credit_card_id = payload.get("credit_card_id")
    is_transfer = payload.get("is_transfer", False)
    destination_account_id = payload.get("destination_account_id")
    
    if not date_str or not description or amount is None:
        raise HTTPException(status_code=400, detail="Missing required transaction parameters")
    
    try:
        t_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format (must be YYYY-MM-DD)")
        
    # Validation of fields
    if not credit_card_id and not account_id:
        raise HTTPException(status_code=400, detail="Transaction must be linked to either a Bank Account or a Credit Card")
        
    if is_transfer and not destination_account_id and not credit_card_id:
        raise HTTPException(status_code=400, detail="Transfer transactions require a destination bank account or credit card")
        
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Insert record
        cursor.execute(
            "INSERT INTO financial_records (date, description, amount, category, account_id, credit_card_id, is_transfer, destination_account_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "RETURNING id, date, description, amount, category, account_id, credit_card_id, is_transfer, destination_account_id",
            (t_date, description, amount, category, account_id, credit_card_id, is_transfer, destination_account_id)
        )
        new_tx = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "success", "transaction": new_tx}
    except Exception as e:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/finance/transactions/delete")
def delete_transaction(payload: Dict[str, Any] = Body(...)):
    tx_id = payload.get("id")
    if tx_id is None:
        raise HTTPException(status_code=400, detail="Missing transaction id")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM financial_records WHERE id = %s", (tx_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "success"}
    except Exception as e:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

# ─── Summary API ──────────────────────────────────────────────────────────────

@app.get("/api/finance/summary")
def get_summary(month: Optional[str] = None):
    """Calculates consolidated net worth, monthly income, monthly expenses, and category breakdown for a given month (YYYY-MM)."""
    if not month:
        month = date.today().strftime("%Y-%m-%d")[:7]
        
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # 1. Total Checking/Savings Balance across all accounts (Sum of current balances of all accounts)
        cursor.execute("""
            SELECT 
                SUM(
                    a.initial_balance + 
                    COALESCE((SELECT SUM(amount) FROM financial_records WHERE account_id = a.id), 0) +
                    COALESCE((SELECT SUM(ABS(amount)) FROM financial_records WHERE destination_account_id = a.id AND is_transfer = TRUE), 0)
                ) as total_accounts_balance
            FROM accounts a
        """)
        total_accounts = cursor.fetchone()["total_accounts_balance"]
        total_accounts = float(total_accounts) if total_accounts else 0.0
        
        # 2. Total Credit Card Outstanding Invoice Debts (All time outstanding)
        cursor.execute("SELECT id, closing_day FROM credit_cards")
        cards = cursor.fetchall()
        total_cards_outstanding = 0.0
        for card in cards:
            cursor.execute("SELECT amount, is_transfer FROM financial_records WHERE credit_card_id = %s", (card["id"],))
            records = cursor.fetchall()
            card_outstanding = 0.0
            for r in records:
                if r["is_transfer"]:
                    card_outstanding -= float(abs(r["amount"]))
                else:
                    card_outstanding += float(abs(r["amount"]))
            total_cards_outstanding += card_outstanding
            
        net_worth = total_accounts - total_cards_outstanding
        
        # 3. Monthly Income and Expenses for the target month
        # We fetch all transactions for this month and categorize them
        cursor.execute("""
            SELECT amount, category, credit_card_id, date, is_transfer
            FROM financial_records
        """)
        all_tx = cursor.fetchall()
        
        monthly_income = 0.0
        monthly_expenses = 0.0
        category_breakdown = {}
        
        for tx in all_tx:
            t_date = tx["date"]
            amount = float(tx["amount"])
            is_transfer = tx["is_transfer"]
            
            # Identify cycle/month
            if tx["credit_card_id"]:
                # Credit card transaction cycle matching
                cursor.execute("SELECT closing_day FROM credit_cards WHERE id = %s", (tx["credit_card_id"],))
                card_row = cursor.fetchone()
                closing_day = card_row["closing_day"] if card_row else 10
                cycle = get_billing_cycle(t_date, closing_day)
            else:
                cycle = t_date.strftime("%Y-%m")
                
            if cycle == month:
                # If it's a transfer (like paying card bill or transferring money), we don't count it as monthly income/expense
                if is_transfer:
                    continue
                    
                if amount > 0:
                    monthly_income += amount
                else:
                    monthly_expenses += abs(amount)
                    cat = tx["category"]
                    category_breakdown[cat] = category_breakdown.get(cat, 0.0) + abs(amount)
                    
        cursor.close()
        conn.close()
        
        return {
            "month": month,
            "total_accounts_balance": total_accounts,
            "total_cards_outstanding": total_cards_outstanding,
            "net_worth": net_worth,
            "monthly_income": monthly_income,
            "monthly_expenses": monthly_expenses,
            "net_monthly_savings": monthly_income - monthly_expenses,
            "category_breakdown": category_breakdown
        }
    except Exception as e:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))
