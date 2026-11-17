#!/usr/bin/env python3
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

POSITIONS = Path("data/positions.json")
TLREF = Path("data/tlref.json")
STOPAJ = 0.175
DAYS_PER_YEAR = 365

positions = json.loads(POSITIONS.read_text(encoding="utf-8"))
tlref = json.loads(TLREF.read_text(encoding="utf-8"))

today = datetime.now(ZoneInfo("Europe/Istanbul")).date()
historical = {
    date.fromisoformat(row["date"]): float(row["rate"])
    for row in tlref.get("historical", [])
    if row.get("date") and row.get("rate") is not None
}
latest_rate = float(tlref["grossAnnualRate"])

def rate_for_day(day):
    if day in historical:
        return historical[day]
    prior = [d for d in historical if d <= day]
    return historical[max(prior)] if prior else latest_rate

for p in positions:
    avg_cost = float(p.get("avgCost") or 0)
    previous_value = float(p.get("realCost") or avg_cost)
    last_updated = p.get("realCostUpdatedAt") or today.isoformat()
    try:
        last_date = date.fromisoformat(last_updated)
    except ValueError:
        last_date = today

    value = previous_value
    daily_added = float(p.get("dailyTlrefCostAdded") or 0) if last_date == today else 0.0

    if last_date < today:
        for offset in range((today - last_date).days):
            day = last_date + timedelta(days=offset)
            value *= 1 + rate_for_day(day) * (1 - STOPAJ) / DAYS_PER_YEAR
        daily_added = value - previous_value

    p["realCost"] = round(value, 4)
    p["tlrefCostAdded"] = round(value - avg_cost, 4)
    p["dailyTlrefCostAdded"] = round(daily_added, 4)
    p["dailyTlrefCostUpdatedAt"] = today.isoformat()
    p["realCostUpdatedAt"] = today.isoformat()

POSITIONS.write_text(json.dumps(positions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

total_daily = sum(float(p.get("dailyTlrefCostAdded", 0) or 0) * float(p.get("qty", 0) or 0) for p in positions)
total_cumulative = sum(float(p.get("tlrefCostAdded", 0) or 0) * float(p.get("qty", 0) or 0) for p in positions)
print(
    f"Real cost updated: {today.isoformat()} | TLREF gross {latest_rate*100:.4f}% | "
    f"net {latest_rate*(1-STOPAJ)*100:.4f}% | daily increase {total_daily:.2f} TL | "
    f"cumulative increase {total_cumulative:.2f} TL | {len(positions)} positions"
)
