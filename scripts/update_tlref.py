#!/usr/bin/env python3
import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path

URL = "https://www.borsaistanbul.com/endeksler/tlref"
OUT = Path("data/tlref.json")
STOPAJ = 0.175
START_DATE = "2025-08-24"

req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")

section = html[html.find("TLREF Verileri"):]
matches = re.findall(r"(\d{2}\.\d{2}\.\d{4}).{0,500}?(\d{2,3}[,.]\d{4})", section, re.S)
rows = []
seen = set()
for d, r in matches:
    iso = datetime.strptime(d, "%d.%m.%Y").date().isoformat()
    if iso in seen:
        continue
    seen.add(iso)
    rows.append({"date": iso, "rate": float(r.replace(",", ".")) / 100})

if not rows:
    raise RuntimeError("TLREF verisi sayfadan ayrıştırılamadı")

rows.sort(key=lambda x: x["date"])
latest = rows[-1]
net_latest = latest["rate"] * (1 - STOPAJ)

payload = {
    "source": URL,
    "asOf": latest["date"],
    "grossAnnualRate": latest["rate"],
    "stopaj": STOPAJ,
    "netAnnualRate": net_latest,
    "startDate": START_DATE,
    "method": "Günlük net TLREF fırsat maliyeti; brüt TLREF üzerinden %17,5 stopaj düşülür ve günlük bileşiklenir.",
    "historical": rows,
    "updatedAt": datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
}
OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
print(f"TLREF {latest['date']} = %{latest['rate']*100:.4f}; net yıllık %{net_latest*100:.4f}; {len(rows)} kayıt")
