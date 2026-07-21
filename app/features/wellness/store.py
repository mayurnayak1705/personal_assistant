"""PostgreSQL storage and deterministic wellness reporting."""
from __future__ import annotations
from datetime import date, datetime, timedelta
from typing import Any
from psycopg.types.json import Jsonb
from app.persistence.postgres_insert import get_connection

REPORT_NUMERIC_FIELDS = (
    "water_l",
    "steps",
    "active_minutes",
    "sleep_hours",
    "mood",
    "weight_kg",
)


def _optional_float(value: Any) -> float | None:
    """Return a usable report number while ignoring blank optional inputs."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def init_wellness_schema() -> None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS wellness_profiles(
          user_id varchar PRIMARY KEY, age int, biological_sex varchar(30), height_cm numeric,
          baseline_weight_kg numeric, current_weight_kg numeric, primary_goal varchar(80),
          target_value numeric, target_unit varchar(30), target_date date, motivation text,
          activity_level varchar(40), dietary_preferences text, restrictions text,
          morning_time time NOT NULL DEFAULT '08:00', evening_time time NOT NULL DEFAULT '20:00',
          created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now());
        CREATE TABLE IF NOT EXISTS wellness_logs(
          id bigserial PRIMARY KEY, user_id varchar NOT NULL, log_date date NOT NULL DEFAULT current_date,
          kind varchar(20) NOT NULL, data jsonb NOT NULL DEFAULT '{}'::jsonb, notes text,
          created_at timestamptz DEFAULT now());
        CREATE INDEX IF NOT EXISTS wellness_logs_user_date ON wellness_logs(user_id, log_date DESC);
        """)
        conn.commit()

def get_profile(user_id: str) -> dict | None:
    init_wellness_schema()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM wellness_profiles WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
    return dict(row) if row else None

def save_profile(user_id: str, values: dict[str, Any]) -> dict:
    init_wellness_schema()
    fields = ["age","biological_sex","height_cm","baseline_weight_kg","current_weight_kg",
              "primary_goal","target_value","target_unit","target_date","motivation","activity_level",
              "dietary_preferences","restrictions","morning_time","evening_time"]
    payload = {key: values.get(key) for key in fields}
    payload["current_weight_kg"] = payload["current_weight_kg"] or payload["baseline_weight_kg"]
    columns = ",".join(payload)
    placeholders = ",".join(["%s"] * len(payload))
    updates = ",".join(f"{key}=EXCLUDED.{key}" for key in payload)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(f"INSERT INTO wellness_profiles(user_id,{columns}) VALUES (%s,{placeholders}) "
                    f"ON CONFLICT(user_id) DO UPDATE SET {updates},updated_at=now() RETURNING *",
                    [user_id, *payload.values()])
        row = cur.fetchone(); conn.commit()
    return dict(row)

def add_log(user_id: str, kind: str, data: dict, notes: str = "", log_date: date | None = None) -> dict:
    if kind not in {"diet","workout","journal","measurement"}: raise ValueError("Invalid wellness log type")
    init_wellness_schema()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO wellness_logs(user_id,log_date,kind,data,notes) VALUES(%s,%s,%s,%s,%s) RETURNING *",
                    (user_id, log_date or date.today(), kind, Jsonb(data), notes))
        row=cur.fetchone(); conn.commit()
    return dict(row)

def report(user_id: str, days: int = 30) -> dict:
    profile=get_profile(user_id); start=date.today()-timedelta(days=max(1,min(days,365))-1)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM wellness_logs WHERE user_id=%s AND log_date>=%s ORDER BY log_date",(user_id,start))
        logs=[dict(r) for r in cur.fetchall()]
    by_day={}
    for log in logs:
        key=log["log_date"].isoformat(); day=by_day.setdefault(key,{"diet":0,"workout":0,"journal":0,"measurement":0,"water_l":0,"steps":0,"active_minutes":0,"sleep_hours":None,"mood":None,"weight_kg":None})
        kind=log.get("kind")
        if kind in {"diet","workout","journal","measurement"}: day[kind]+=1
        data=log.get("data") if isinstance(log.get("data"),dict) else {}
        for field in REPORT_NUMERIC_FIELDS:
            number=_optional_float(data.get(field))
            if number is not None: day[field]=number
    workout_days=sum(1 for d in by_day.values() if d["workout"]); diet_days=sum(1 for d in by_day.values() if d["diet"]); journal_days=sum(1 for d in by_day.values() if d["journal"])
    weights=[d["weight_kg"] for d in by_day.values() if d["weight_kg"] is not None]
    current=weights[-1] if weights else float(profile.get("current_weight_kg") or 0) if profile else None
    target=float(profile.get("target_value") or 0) if profile else None; baseline=float(profile.get("baseline_weight_kg") or 0) if profile else None
    progress=None
    if baseline and current is not None and target and baseline != target: progress=max(0,min(100,abs(current-baseline)/abs(target-baseline)*100))
    ordered=sorted(by_day); streak=0
    cursor=date.today()
    while cursor.isoformat() in by_day and any(by_day[cursor.isoformat()][k] for k in ("diet","workout","journal")):
        streak+=1; cursor-=timedelta(days=1)
    def average(field, keys):
        values=[by_day[k][field] for k in keys if by_day[k][field] is not None]
        return round(sum(values)/len(values),2) if values else None
    this_week=[k for k in ordered if date.fromisoformat(k)>=date.today()-timedelta(days=6)]
    last_week=[k for k in ordered if date.today()-timedelta(days=13)<=date.fromisoformat(k)<date.today()-timedelta(days=6)]
    height=float(profile.get("height_cm") or 0) if profile else 0; age=float(profile.get("age") or 0) if profile else 0
    bmi=round(current/((height/100)**2),1) if current and height else None
    sex=(profile.get("biological_sex") or "").casefold() if profile else ""
    bmr=round(10*current+6.25*height-5*age+(5 if sex=="male" else -161)) if current and height and age and sex in {"male","female"} else None
    return {"profile":profile,"period_days":days,"summary":{"workout_days":workout_days,"diet_log_days":diet_days,"journal_days":journal_days,"active_minutes":sum(d["active_minutes"] for d in by_day.values()),"steps":sum(d["steps"] for d in by_day.values()),"consistency_streak_days":streak,"goal_progress_percent":progress,"current_value":current,"target_value":target,"bmi":bmi,"estimated_bmr":bmr,"this_week":{"sleep_hours":average("sleep_hours",this_week),"mood":average("mood",this_week),"weight_kg":average("weight_kg",this_week)},"last_week":{"sleep_hours":average("sleep_hours",last_week),"mood":average("mood",last_week),"weight_kg":average("weight_kg",last_week)}},"daily":[{"date":k,**v} for k,v in by_day.items()]}

def due_prompts(user_id: str, now: datetime | None = None) -> list[dict]:
    profile=get_profile(user_id)
    if not profile: return [{"type":"setup","title":"Set up Wellness","message":"Tell me your goals, baseline, diet and activity preferences to begin."}]
    now=now or datetime.now(); prompts=[]
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT kind FROM wellness_logs WHERE user_id=%s AND log_date=current_date",(user_id,)); kinds={r["kind"] for r in cur.fetchall()}
    if now.time() >= profile["morning_time"] and "measurement" not in kinds:
        prompts.append({"type":"morning","title":"Morning wellness check-in","message":f"Your goal is {profile['primary_goal']}. Log sleep, mood, weight or today's plan."})
    if now.time() >= profile["evening_time"] and not {"diet","workout","journal"}.issubset(kinds):
        prompts.append({"type":"evening","title":"Evening wellness journal","message":"Log today’s meals, activity, mood and reflection."})
    return prompts
