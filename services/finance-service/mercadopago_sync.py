import os
import io
import csv
import time
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta

DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "lucas_todo")
DB_USER = os.getenv("POSTGRES_USER", "lucas_user")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "lucas_password")

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )

def map_headers(headers):
    mapping = {}
    for idx, h in enumerate(headers):
        h_upper = h.upper().strip().replace('"', '').replace("'", "")
        # Date matches
        if h_upper in ['DATE', 'DATA', 'DATE_CREATED', 'DATE_RELEASE', 'DATA_LIBERACAO', 'DATA_CRIACAO']:
            mapping['date'] = idx
        # ID matches
        elif h_upper in ['SOURCE_ID', 'ID', 'SOURCE', 'ID_TRANSACAO', 'ID_OPERACAO', 'EXTERNAL_REFERENCE']:
            if 'id' not in mapping or h_upper != 'EXTERNAL_REFERENCE':
                mapping['id'] = idx
        # Description matches
        elif h_upper in ['DESCRIPTION', 'DESCRICAO', 'DESCRITIVO', 'DETALHE', 'RECORD_TYPE', 'CONCEITO']:
            if 'description' not in mapping or h_upper == 'DESCRIPTION':
                mapping['description'] = idx
        # Credit matches
        elif h_upper in ['NET_CREDIT_AMOUNT', 'VALOR_LIQUIDO_CREDITO', 'NET_CREDIT', 'CREDITO', 'CREDIT', 'VALOR_CREDITO']:
            mapping['credit'] = idx
        # Debit matches
        elif h_upper in ['NET_DEBIT_AMOUNT', 'VALOR_LIQUIDO_DEBITO', 'NET_DEBIT', 'DEBITO', 'DEBIT', 'VALOR_DEBITO']:
            mapping['debit'] = idx
        # Gross matches (as fallback)
        elif h_upper in ['GROSS_AMOUNT', 'VALOR_BRUTO', 'AMOUNT', 'VALOR']:
            mapping['gross'] = idx
    return mapping

# Global status tracker for the background task
SYNC_STATUS = {
    "status": "idle", # "idle", "running", "success", "error"
    "last_sync": None,
    "imported_count": 0,
    "error_message": None
}

def sync_mercado_pago_task(access_token: str, account_id: int):
    global SYNC_STATUS
    SYNC_STATUS["status"] = "running"
    SYNC_STATUS["error_message"] = None
    SYNC_STATUS["imported_count"] = 0
    
    try:
        # Request report for the last 15 days to ensure we get all cleared transactions
        end_dt = datetime.now()
        begin_dt = end_dt - timedelta(days=15)
        
        begin_str = begin_dt.strftime("%Y-%m-%dT00:00:00Z")
        end_str = end_dt.strftime("%Y-%m-%dT23:59:59Z")
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "begin_date": begin_str,
            "end_date": end_str
        }
        
        print(f"[MP Sync] Generating release report from {begin_str} to {end_str}", flush=True)
        # 1. Request report generation
        response = requests.post(
            "https://api.mercadopago.com/v1/account/release_report",
            headers=headers,
            json=payload,
            timeout=15
        )
        
        if response.status_code not in [200, 201, 202]:
            raise Exception(f"Failed to request report from Mercado Pago. HTTP {response.status_code}: {response.text}")
            
        # 2. Poll report list to find the ready download url
        download_url = None
        report_id = None
        
        # Try to parse response json to get the task ID or name if provided
        try:
            resp_data = response.json()
            report_id = resp_data.get("id")
        except:
            pass
            
        print(f"[MP Sync] Report request accepted. Report ID: {report_id}. Waiting for completion...", flush=True)
        
        # Poll for 2 minutes max (40 attempts, 3s sleep)
        file_name = None
        for attempt in range(40):
            time.sleep(3)
            list_resp = requests.get(
                "https://api.mercadopago.com/v1/account/release_report/list",
                headers=headers,
                timeout=15
            )
            if list_resp.status_code != 200:
                print(f"[MP Sync] Warning: failed to list reports. HTTP {list_resp.status_code}", flush=True)
                continue
                
            reports = list_resp.json()
            print(f"[MP Sync] Attempt {attempt+1}: Received reports list: {reports}", flush=True)
            
            if not isinstance(reports, list):
                if isinstance(reports, dict) and "results" in reports:
                    reports = reports["results"]
                else:
                    reports = []
                    
            if not reports:
                continue
                
            # Sort reports by generation_date desc to get the newest first
            try:
                reports_sorted = sorted(reports, key=lambda x: x.get("generation_date", x.get("date_created", "")), reverse=True)
            except:
                reports_sorted = reports
                
            newest_report = reports_sorted[0]
            
            # If we have a specific report_id, find it; otherwise take the newest completed report
            target_report = None
            if report_id:
                for rep in reports_sorted:
                    if str(rep.get("id")) == str(report_id):
                        target_report = rep
                        break
            
            if not target_report:
                target_report = newest_report
                
            status = str(target_report.get("status", "")).lower()
            print(f"[MP Sync] Attempt {attempt+1}: Target report ID: {target_report.get('id')}, Status is '{status}'", flush=True)
            
            if status in ["enabled", "processed", "available", "file_generated", "success"]:
                file_name = target_report.get("file_name")
                if file_name:
                    break
                
        if not file_name:
            raise Exception("Timeout waiting for Mercado Pago report generation. Please try again in a few moments.")
            
        download_url = f"https://api.mercadopago.com/v1/account/release_report/{file_name}"
        print(f"[MP Sync] Report ready! Downloading file '{file_name}' from: {download_url}", flush=True)
        
        # 3. Download CSV
        csv_resp = requests.get(download_url, headers=headers, timeout=30)
        if csv_resp.status_code != 200:
            raise Exception(f"Failed to download report file '{file_name}' from Mercado Pago. HTTP {csv_resp.status_code}: {csv_resp.text}")
            
        csv_content = csv_resp.text
        
        # 4. Parse CSV
        f = io.StringIO(csv_content)
        reader = csv.reader(f)
        
        # Read header row
        try:
            headers_row = next(reader)
        except StopIteration:
            raise Exception("Downloaded report CSV is empty")
            
        mapping = map_headers(headers_row)
        print(f"[MP Sync] Header mapping: {mapping}", flush=True)
        
        if 'date' not in mapping or 'id' not in mapping or ('credit' not in mapping and 'gross' not in mapping):
            raise Exception(f"Could not map required CSV headers. Headers found: {headers_row}")
            
        imported = 0
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            for row in reader:
                if not row or len(row) <= max(mapping.values()):
                    continue
                    
                ext_id = str(row[mapping['id']]).strip()
                date_raw = row[mapping['date']].strip()
                
                # Check description
                desc = "Mercado Pago Transação"
                if 'description' in mapping:
                    desc = row[mapping['description']].strip()
                    
                # Calculate amount
                credit = 0.0
                debit = 0.0
                gross = 0.0
                
                if 'credit' in mapping and row[mapping['credit']].strip():
                    try:
                        credit = float(row[mapping['credit']].strip().replace(',', '.'))
                    except:
                        pass
                if 'debit' in mapping and row[mapping['debit']].strip():
                    try:
                        debit = float(row[mapping['debit']].strip().replace(',', '.'))
                    except:
                        pass
                if 'gross' in mapping and row[mapping['gross']].strip():
                    try:
                        gross = float(row[mapping['gross']].strip().replace(',', '.'))
                    except:
                        pass
                        
                # Determine final transaction amount
                if 'credit' in mapping or 'debit' in mapping:
                    amount = credit - debit
                else:
                    amount = gross
                    
                # Skip 0 amount adjustments
                if abs(amount) < 0.001:
                    continue
                    
                # Parse date-time
                try:
                    dt_part = date_raw.replace('T', ' ').split('.')[0].split('-0')[0].split('+0')[0].strip()
                    t_date = datetime.strptime(dt_part, "%Y-%m-%d %H:%M:%S")
                except:
                    try:
                        t_date = datetime.strptime(date_raw.split(' ')[0], "%Y-%m-%d")
                    except:
                        t_date = datetime.now()
                        
                # Check if transaction already exists in the database
                cursor.execute("SELECT id FROM financial_records WHERE external_id = %s", (ext_id,))
                exists = cursor.fetchone()
                
                if not exists:
                    # Insert the transaction
                    cursor.execute(
                        "INSERT INTO financial_records (date, description, amount, category, account_id, external_id) "
                        "VALUES (%s, %s, %s, 'Outros', %s, %s)",
                        (t_date, desc, amount, account_id, ext_id)
                    )
                    imported += 1
                    
            conn.commit()
            cursor.close()
            conn.close()
            
            print(f"[MP Sync] Sync finished successfully. Imported {imported} new transactions.", flush=True)
            SYNC_STATUS["status"] = "success"
            SYNC_STATUS["last_sync"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            SYNC_STATUS["imported_count"] = imported
            
        except Exception as db_ex:
            conn.rollback()
            cursor.close()
            conn.close()
            raise db_ex
            
    except Exception as e:
        print(f"[MP Sync] Error: {e}", flush=True)
        SYNC_STATUS["status"] = "error"
        SYNC_STATUS["error_message"] = str(e)
