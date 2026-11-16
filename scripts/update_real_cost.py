#!/usr/bin/env python3
import json
import math
from datetime import date, datetime
from pathlib import Path

POSITIONS = Path("data/positions.json")
TLREF = Path("data/tlref.json")
STOPAJ = 0.175
DAYS_PER_YEAR = 365

positions = json.loads(POSITIONS.read_text(encoding="utf-8"))
tlref = json.loads(TLREF.read_text(encoding="utf-8"))

today = date.today()
latest_rate = float(tlref["grossAnnualRate"])
net_annual = latest_rate * (1 - STOPAJ)

for p in positions:
    base_date = p.get("realCostBaseDate")
    if not base_date:
        base_date = today.isoformat()
        p["realCostBaseDate"] = base_date

    start = date.fromisoformat(base_date)
    days = max(0, (today - start).days)
    factor = (1 + net_annual / DAYS_PER_YEAR) ** days
    p["realCost"] = round(float(p["avgCost"]) * factor, 4)

POSITIONS.write_text(json.dumps(positions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print(
    f"Reel maliyet güncellendi: {today.isoformat()} | "
    f"TLREF %{latest_rate*100:.4f} | net %{net_annual*100:.4f} | "
    f"{len(positions)} pozisyon"
)
