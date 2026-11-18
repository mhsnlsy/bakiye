#!/usr/bin/env python3
import json
import time
import urllib.request

API = "https://bakiye.muhsin-ulusoy.workers.dev/api/quotes"

def fetch():
    url = API + "?snapshot=" + str(int(time.time()))
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "BakiyeSnapshot/1.0",
            "Accept": "application/json",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def main():
    q = fetch()
    prices = q.get("quotes", {})
    required = ["TAVHL", "KARSN", "THYAO", "CGCAM", "SISE", "ZPLIB.F"]
    missing = [s for s in required if not isinstance(prices.get(s), (int, float)) or prices[s] <= 0]
    if missing:
        raise SystemExit("Live quote API missing: " + ",".join(missing))

    gold = q.get("goldGramTRY")
    if not isinstance(gold, (int, float)) or gold <= 0:
        raise SystemExit("Live Doviz.com gram-gold price missing")

    fx = q.get("fx", {})
    missing_fx = [c for c in ["USDTRY", "EURTRY", "GBPTRY"] if not isinstance(fx.get(c), (int, float)) or fx[c] <= 0]
    if missing_fx:
        raise SystemExit("Live FX missing: " + ",".join(missing_fx))

    with open("/tmp/quotes.json", "w", encoding="utf-8") as f:
        json.dump(q, f, ensure_ascii=False, indent=2)

    print("Live quotes loaded from Worker API")
    print("Stocks:", {s: prices[s] for s in required})
    print("Gold:", gold)
    print("FX:", {c: fx[c] for c in ["USDTRY", "EURTRY", "GBPTRY"]})
    print("lastRefresh:", q.get("lastRefresh"))
    print("goldPriceFetchedAt:", q.get("goldPriceFetchedAt"))

if __name__ == "__main__":
    main()
