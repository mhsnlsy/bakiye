#!/usr/bin/env python3
import json, re, urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

TV_URL = "https://tr.tradingview.com/symbols/BIST-TLREF/"
TV_SCAN_URL = "https://scanner.tradingview.com/turkey/scan"
OUT = Path("data/tlref.json")
STOPAJ = 0.175
START_DATE = "2025-08-24"

def tv_tlref():
    payload = {
        "columns": ["close", "change", "change_abs", "exchange", "type", "name", "description"],
        "symbols": {"tickers": ["BIST:TLREF"]},
        "range": [0, 1]
    }
    req = urllib.request.Request(
        TV_SCAN_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "text/plain;charset=UTF-8",
            "Accept": "application/json",
            "Origin": "https://www.tradingview.com",
            "Referer": TV_URL,
            "User-Agent": "Mozilla/5.0"
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data=json.loads(r.read().decode("utf-8"))
    for row in data.get("data", []):
        if row.get("s") == "BIST:TLREF":
            vals=row.get("d", [])
            rate=float(vals[0])
            if 20 < rate < 60:
                return rate / 100
    raise RuntimeError("TradingView BIST:TLREF verisi bulunamadı")

today=datetime.now(ZoneInfo("Europe/Istanbul")).date().isoformat()
rate=tv_tlref()

previous=[]
if OUT.exists():
    try:
        previous=json.loads(OUT.read_text(encoding="utf-8")).get("historical", [])
    except Exception:
        previous=[]

merged={r["date"]:float(r["rate"]) for r in previous if r.get("date") and r.get("rate") is not None}
merged[today]=rate
historical=[{"date":d,"rate":merged[d]} for d in sorted(merged)]
net=rate*(1-STOPAJ)

payload={
    "source":"TradingView BIST:TLREF",
    "sourceUrl":TV_URL,
    "asOf":today,
    "grossAnnualRate":rate,
    "stopaj":STOPAJ,
    "netAnnualRate":net,
    "startDate":START_DATE,
    "historical":historical,
    "updatedAt":datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z"),
    "todayAvailable":True,
    "method":"Günlük net TLREF fırsat maliyeti; TradingView BIST:TLREF üzerinden brüt TLREF, %17,5 stopaj sonrası netleştirilir ve günlük bileşiklenir."
}
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"
",encoding="utf-8")
print(f"TradingView BIST:TLREF {today} = %{rate*100:.4f}; net yıllık %{net*100:.4f}; {len(historical)} kayıt")
