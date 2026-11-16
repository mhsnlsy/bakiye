#!/usr/bin/env python3
import json
from datetime import date, datetime, timedelta
from pathlib import Path

BAL = Path("data/balance.json")
QUOTES = Path("data/quotes.json")
POSITIONS = Path("data/positions.json")
TLREF = Path("data/tlref.json")
HISTORY = Path("data/history.json")

balance=json.loads(BAL.read_text(encoding="utf-8"))
quotes=json.loads(QUOTES.read_text(encoding="utf-8"))
positions=json.loads(POSITIONS.read_text(encoding="utf-8"))
tlref=json.loads(TLREF.read_text(encoding="utf-8"))

q=quotes.get("quotes",{})
fx=quotes.get("fx",{})
stocks=funds=0.0
for p in positions:
    v=float(p.get("qty",0))*float(q.get(p["symbol"],p.get("snapshotPrice",0)))
    if p.get("type")=="fund":
        funds += v
    else:
        stocks += v

a=balance.get("accounts",{})
tl=sum(float(x.get("value",0)) for x in a.values() if x.get("category")=="try")
d=a.get("doviz",{}).get("currencies",{})
bd=a.get("bankaDoviz",{}).get("currencies",{})
cash_fx=sum(float(d.get(code,0))*float(fx.get(code+"TRY",0)) for code in ("USD","EUR","GBP"))
bank_fx=float(bd.get("EUR",0))*float(fx.get("EURTRY",0))
gold=sum(float(x.get("value",0)) for x in a.values() if x.get("category")=="gold")
receivable=sum(float(x.get("value",0)) for x in a.values() if x.get("category")=="receivable")
total=stocks+funds+tl+cash_fx+bank_fx+gold+receivable

today=date.today().isoformat()
net_annual=float(tlref.get("netAnnualRate",0))
real_cost_total=0.0
for p in positions:
    base=float(p.get("avgCost",0))
    start=date.fromisoformat(p.get("realCostBaseDate",today))
    days=max(0,(date.today()-start).days)
    real_unit=base*((1+net_annual/365)**days)
    real_cost_total += real_unit*float(p.get("qty",0))
real_cost_total=round(real_cost_total,2)
nominal_cost_total=round(sum(float(p.get("avgCost",0))*float(p.get("qty",0)) for p in positions),2)
tlref_cost_added=round(real_cost_total-nominal_cost_total,2)
try:
    h=json.loads(HISTORY.read_text(encoding="utf-8"))
except Exception:
    h={"version":1,"frequency":"daily","startDate":today,"retentionDays":365,"snapshots":[]}

snap={"date":today,"total":round(total,2),"stocks":round(stocks,2),"funds":round(funds,2),
      "try":round(tl,2),"cashFx":round(cash_fx,2),"bankFx":round(bank_fx,2),
      "gold":round(gold,2),"receivable":round(receivable,2),"realCostTotal":real_cost_total,"nominalCostTotal":nominal_cost_total,"tlrefCostAdded":tlref_cost_added,"netTlrefAnnualRate":net_annual}

rows=[x for x in h.get("snapshots",[]) if x.get("date")!=today]
rows.append(snap)
rows.sort(key=lambda x:x["date"])
cutoff=date.today()-timedelta(days=int(h.get("retentionDays",365))-1)
rows=[x for x in rows if date.fromisoformat(x["date"])>=cutoff]

h["startDate"]=rows[0]["date"] if rows else today
h["updatedAt"]=datetime.now().astimezone().replace(microsecond=0).isoformat()
h["snapshots"]=rows
HISTORY.write_text(json.dumps(h,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(f"Balance history: {today} total={total:.2f}; snapshots={len(rows)}")
