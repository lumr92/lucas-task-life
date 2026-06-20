import re
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from fastapi import FastAPI
import requests
from icalendar import Calendar as iCal
import recurring_ical_events

app = FastAPI(title="Lucas_OS Calendar Service", version="2.0.0")

GAMIFICATION_SVC_URL = "http://gamification-service:9003"

def get_settings_from_gami() -> Dict[str, Any]:
    try:
        r = requests.get(f"{GAMIFICATION_SVC_URL}/api/settings", timeout=2)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"Error fetching settings from gamification-service: {e}")
    return {}

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

@app.get("/api/calendar")
def get_calendar():
    config = get_settings_from_gami()
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
