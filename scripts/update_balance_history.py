#!/usr/bin/env python3
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

BAL = Path("data/balance.json")
QUOTES = Path("data/quotes.json")
POSITIONS = Path("data/positions.json")
TLREF = Path("data/tlref.json")
HISTORY = Path("data/history.json")

balance = json.loads(BAL.read_text(encoding="utf-8"))
quotes = json.loads(QUOTES.read_text(encoding="utf-8"))
positions = json.loads(POSITIONS.read_text(encoding="utf-8"))
tlref = json.loads(TLREF.read_text(encoding="utf-8"))

q = quotes.get("quotes", {})
fx = quotes.get("fx", {})
today = datetime.now(ZoneInfo("Europe/Istanbul")).date()
today_key = today.isoformat()

missing = [
    p.get("symbol") for p in positions
    if not isinstance(q.get(p.get("symbol")), (int, float))
    or q.get(p.get("symbol"), 0) <= 0
]
if missing:
    raise SystemExit("Snapshot refused; missing current quotes: " + ", ".join(missing))

stocks = funds = 0.0
real_cost_total = nominal_cost_total = daily_cost_total = 0.0
daily_cost_ready = bool(positions)

for p in positions:
    qty = float(p.get("qty", 0) or 0)
    market_value = qty * float(q[p["symbol"]])
    if p.get("type") == "fund":
        funds += market_value
    else:
        stocks += market_value

    avg_cost = float(p.get("avgCost", 0) or 0)
    real_cost = float(p.get("realCost", avg_cost) or avg_cost)
    nominal_cost_total += avg_cost * qty
    real_cost_total += real_cost * qty
    daily_cost_total += float(p.get("dailyTlrefCostAdded", 0) or 0) * qty
    if p.get("dailyTlrefCostUpdatedAt") != today_key:
        daily_cost_ready = False

a = balance.get("accounts", {})
try_value = sum(float(x.get("value", 0) or 0) for x in a.values() if x.get("category") == "try")

def fx_value(account_id):
    currencies = (a.get(account_id) or {}).get("currencies") or {}
    return sum(float(qty or 0) * float(fx.get(code + "TRY", 0) or 0) for code, qty in currencies.items())

cash_fx = fx_value("doviz")
bank_fx = fx_value("bankaDoviz")
gold = sum(float(x.get("value", 0) or 0) for x in a.values() if x.get("category") == "gold")
receivable = sum(float(x.get("value", 0) or 0) for x in a.values() if x.get("category") == "receivable")

components = {
    "stocks": round(stocks, 2),
    "funds": round(funds, 2),
    "try": round(try_value, 2),
    "cashFx": round(cash_fx, 2),
    "bankFx": round(bank_fx, 2),
    "gold": round(gold, 2),
    "receivable": round(receivable, 2),
}
total = round(sum(components.values()), 2)
nominal_cost_total = round(nominal_cost_total, 2)
real_cost_total = round(real_cost_total, 2)
cumulative_cost = round(real_cost_total - nominal_cost_total, 2)
daily_cost = round(daily_cost_total, 2) if daily_cost_ready else 0.0

snap = {
    "date": today_key,
    "total": total,
    **components,
    "realCostTotal": real_cost_total,
    "nominalCostTotal": nominal_cost_total,
    "tlrefCostAdded": daily_cost,
    "tlrefDailyCostAdded": daily_cost,
    "tlrefDailyCostAvailable": daily_cost_ready,
    "tlrefCumulativeCostAdded": cumulative_cost,
    "netTlrefAnnualRate": float(tlref.get("netAnnualRate", 0) or 0),
    "tlrefAsOf": tlref.get("asOf"),
}

try:
    history = json.loads(HISTORY.read_text(encoding="utf-8"))
except Exception:
    history = {"version": 1, "frequency": "daily", "startDate": today_key, "retentionDays": 700, "snapshots": [], "weeklySnapshots": []}

rows = [x for x in history.get("snapshots", []) if x.get("date") != today_key]
rows.append(snap)

if today.weekday() == 6:
    weekly = [x for x in history.get("weeklySnapshots", []) if x.get("date") != today_key]
    weekly.append(snap)
    weekly.sort(key=lambda x: x["date"])
    history["weeklySnapshots"] = weekly

rows.sort(key=lambda x: x["date"])
cutoff = today - timedelta(days=int(history.get("retentionDays", 700)) - 1)
rows = [x for x in rows if datetime.fromisoformat(x["date"]).date() >= cutoff]

history["startDate"] = rows[0]["date"] if rows else today_key
history["updatedAt"] = datetime.now(ZoneInfo("Europe/Istanbul")).replace(microsecond=0).isoformat()
history["snapshots"] = rows
history.setdefault("weeklySnapshots", [])
HISTORY.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print(f"Balance history: {today_key} total={total:.2f}; component sum={sum(components.values()):.2f}; daily TLREF increase={daily_cost:.2f}; cumulative TLREF cost={cumulative_cost:.2f}; snapshots={len(rows)}")
