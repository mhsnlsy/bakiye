#!/usr/bin/env python3
import json
from datetime import date, datetime
from pathlib import Path

POSITIONS = Path("data/positions.json")
TLREF = Path("data/tlref.json")
STOPAJ = 0.175
DAYS_PER_YEAR = 365

positions = json.loads(POSITIONS.read_text(encoding="utf-8"))
tlref = json.loads(TLREF.read_text(encoding="utf-8"))

today = date.today()
historical = {date.fromisoformat(r["date"]): float(r["rate"]) for r in tlref.get("historical", []) if r.get("date") and r.get("rate") is not None}
latest_rate = float(tlref["grossAnnualRate"])

def rate_for_day(day):
    if day in historical:
        return historical[day]
    prior = [d for d in historical if d <= day]
    return historical[max(prior)] if prior else latest_rate

for p in positions:
    base_date = p.get("realCostBaseDate")
    if not base_date:
        base_date = p.get("purchaseDate") or today.isoformat()
        p["purchaseDate"] = base_date
        p["realCostBaseDate"] = base_date

    start = date.fromisoformat(base_date)
    days = max(0, (today - start).days)
    factor = 1.0
    for offset in range(days):
        day = start + __import__("datetime").timedelta(days=offset)
        factor *= 1 + rate_for_day(day) * (1 - STOPAJ) / DAYS_PER_YEAR
    p["realCost"] = round(float(p["avgCost"]) * factor, 4)
    p["tlrefCostAdded"] = round(p["realCost"] - float(p["avgCost"]), 4)
    p["realCostUpdatedAt"] = today.isoformat()

POSITIONS.write_text(json.dumps(positions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print(
    f"Reel maliyet güncellendi: {today.isoformat()} | "
    f"TLREF %{latest_rate*100:.4f} | net %{latest_rate*(1-STOPAJ)*100:.4f} | "
    f"{len(positions)} pozisyon"
)
