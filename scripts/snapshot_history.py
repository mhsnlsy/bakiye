import json
from datetime import datetime, timezone

def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def main():
    balance=load("/tmp/balance.json")
    quotes=load("/tmp/quotes.json")
    positions=load("/tmp/positions.json")
    tlref=load("/tmp/tlref.json")

    q=quotes.get("quotes", {})
    rates=quotes.get("fx", {})
    rows=[]
    for p in positions if isinstance(positions,list) else []:
        symbol=p.get("symbol")
        qty=float(p.get("qty",0) or 0)
        price=float(q.get(symbol,p.get("snapshotPrice",0)) or 0)
        rows.append((symbol,qty,price))

    stocks=sum(qty*price for _,qty,price in rows)
    a=balance.get("accounts",{})
    try_val=sum(float(x.get("value",0) or 0) for x in a.values() if x.get("category")=="try")
    def fxval(account_id):
        x=a.get(account_id,{})
        return sum(float(qty or 0)*float(rates.get(code+"TRY",0) or 0) for code,qty in (x.get("currencies") or {}).items())
    cash_fx=fxval("doviz")
    bank_fx=fxval("bankaDoviz")
    gold=float((a.get("nkolayAltin") or {}).get("value",0) or 0)
    receivable=float((a.get("tahminiAlacak") or {}).get("value",0) or 0)
    total=stocks+try_val+cash_fx+bank_fx+gold+receivable

    now=datetime.now(timezone.utc)
    date=now.astimezone(__import__("zoneinfo").ZoneInfo("Europe/Istanbul")).date().isoformat()
    entry={
        "date":date,
        "capturedAt":now.isoformat().replace("+00:00","Z"),
        "snapshotTime":"18:40 Europe/Istanbul",
        "total":round(total,2),
        "stocks":round(stocks,2),
        "funds":0,
        "try":round(try_val,2),
        "cashFx":round(cash_fx,2),
        "bankFx":round(bank_fx,2),
        "gold":round(gold,2),
        "receivable":round(receivable,2),
        "tlrefCostAdded":0,
        "tlrefAsOf":tlref.get("asOf"),
        "tlrefGrossAnnualRate":tlref.get("grossAnnualRate"),
        "tlrefNetAnnualRate":tlref.get("netAnnualRate")
    }

    try:
        history=load("/tmp/history.json")
    except FileNotFoundError:
        history={"version":1,"frequency":"daily","startDate":date,"retentionDays":700,"updatedAt":None,"snapshots":[]}

    snaps=[s for s in history.get("snapshots",[]) if s.get("date")!=date]
    snaps.append(entry)
    snaps.sort(key=lambda x:x.get("date",""))
    history["snapshots"]=snaps[-700:]
    history["retentionDays"]=700
    history["updatedAt"]=now.isoformat()
    history["frequency"]="daily"
    history["snapshotTime"]="18:40 Europe/Istanbul"
    history["startDate"]=history["snapshots"][0]["date"] if history["snapshots"] else date

    with open("/tmp/history.json","w",encoding="utf-8") as f:
        json.dump(history,f,ensure_ascii=False,indent=2)
    print("18:40 snapshot:",entry)
    print("Snapshots:",len(history["snapshots"]))

if __name__=="__main__":
    main()
