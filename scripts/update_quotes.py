#!/usr/bin/env python3
import json, re, urllib.request
from datetime import datetime, timezone

Midas URL = "https://www.getmidas.com/canli-borsa/tum-hisseler"
DOVIZ_URL = "https://www.doviz.com/"

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "ignore")

def price_from_table(html, symbol):
    pat = rf"{re.escape(symbol)}\\s*\\|\\s*([0-9.,]+)"
    m = re.search(pat, html, re.I)
    if not m:
        pat = rf"{re.escape(symbol)}.*?([0-9]+,[0-9]+)"
        m = re.search(pat, html, re.I | re.S)
    if not m:
        return None
    return float(m.group(1).replace(".", "").replace(",", "."))

def main():
    with open("data/quotes.json", encoding="utf-8") as f:
        data = json.load(f)

    midas = get(MIDAS_URL)
    doviz = get(DOVIZ_URL)

    symbols = ["TAVHL", "KARSN", "THYAO", "CGCAM", "SISE"]
    updated = []
    for s in symbols:
        p = price_from_table(midas, s)
        if p is not None:
            data["quotes"][s] = p
            updated.append(s)

    for code in ["USD", "EUR", "GBP"]:
        p = price_from_table(doviz, code)
        if p is not None:
            data["fx"][code + "TRY"] = p
            updated.append(code + "TRY")

    data["asOf"] = datetime.now(timezone.utc).isoformat()
    data["source"] = "Midas Canlı Borsa (15 dk gecikmeli) + Döviz.com serbest piyasa"
    data["sourceUrl"] = MIDAS_URL
    data["fxSourceUrl"] = DOVIZ_URL
    data["lastRefresh"] = datetime.now(timezone.utc).isoformat()
    data["updatedSymbols"] = updated

    with open("data/quotes.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("Updated:", ", ".join(updated))

if __name__ == "__main__":
    main()
