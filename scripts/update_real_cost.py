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
    # realCost is the authoritative accumulated real cost.
    # Each daily run compounds it from the last update date using the
    # TLREF rate for each elapsed calendar day. Do NOT reconstruct it
    # from avgCost: purchase dates are not stored in this portfolio.
    last_updated = p.get("realCostUpdatedAt") or today.isoformat()
    try:
        last_date = date.fromisoformat(last_updated)
    except ValueError:
        last_date = today

    value = float(p.get("realCost") or p.get("avgCost") or 0)
    if last_date < today:
        for offset in range((today - last_date).days):
            day = last_date + __import__("datetime").timedelta(days=offset)
            value *= 1 + rate_for_day(day) * (1 - STOPAJ) / DAYS_PER_YEAR

    p["realCost"] = round(value, 4)
    p["tlrefCostAdded"] = round(value - float(p["avgCost"]), 4)
    p["realCostUpdatedAt"] = today.isoformat()

POSITIONS.write_text(json.dumps(positions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print(
    f"Reel maliyet güncellendi: {today.isoformat()} | "
    f"TLREF %{latest_rate*100:.4f} | net %{latest_rate*(1-STOPAJ)*100:.4f} | "
    f"{len(positions)} pozisyon"
)
