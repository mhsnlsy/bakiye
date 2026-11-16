import json, os, urllib.request
from datetime import datetime, timezone

ARCHIVE="/tmp/stock-closing-history.json"
R2_KEY="history/stock-closing.json"
SYMBOLS=["TAVHL","KARSN","THYAO","CGCAM","SISE","ZPLIB.F"]

def get(url):
    req=urllib.request.Request(url, headers={
        "User-Agent":"Mozilla/5.0",
        "Accept":"application/json",
        "Cache-Control":"no-cache"
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

def main():
    with open("/tmp/quotes.json", encoding="utf-8") as f:
        q=json.load(f)

    prices=q.get("quotes", {})
    missing=[s for s in SYMBOLS if not isinstance(prices.get(s), (int,float)) or prices[s] <= 0]
    if missing:
        raise SystemExit("Missing closing prices: "+",".join(missing))

    now=datetime.now(timezone.utc)
    date=now.date().isoformat()
    entry={
        "date":date,
        "capturedAt":now.isoformat().replace("+00:00","Z"),
        "source":q.get("source","Uzmanpara"),
        "sourceUrl":q.get("sourceUrl",""),
        "prices":{s:float(prices[s]) for s in SYMBOLS}
    }

    try:
        with open(ARCHIVE, encoding="utf-8") as f:
            archive=json.load(f)
    except FileNotFoundError:
        archive={"version":1,"retentionDays":30,"updatedAt":None,"entries":[]}

    entries=[e for e in archive.get("entries",[]) if e.get("date") != date]
    entries.append(entry)
    entries.sort(key=lambda e:e.get("date",""))
    entries=entries[-30:]

    archive={
        "version":1,
        "retentionDays":30,
        "updatedAt":now.isoformat().replace("+00:00","Z"),
        "entries":entries
    }

    with open(ARCHIVE,"w",encoding="utf-8") as f:
        json.dump(archive,f,ensure_ascii=False,indent=2)

    print("Archived:", date)
    print("Prices:", entry["prices"])
    print("Archive entries:", len(entries))

if __name__=="__main__":
    main()
