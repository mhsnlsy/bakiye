import json, re, html, os, sys, urllib.request
from html.parser import HTMLParser
from datetime import datetime, timezone

STOCK_SOURCE = "https://uzmanpara.milliyet.com.tr/canli-borsa/?endex=xutum"
STOCKS = ["TAVHL","KARSN","THYAO","CGCAM","SISE","ZPLIB.F"]

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows=[]; self.row=[]; self.cell=[]; self.in_td=False; self.in_tr=False
    def handle_starttag(self, tag, attrs):
        if tag.lower()=="tr":
            self.in_tr=True; self.row=[]
        elif tag.lower()=="td" and self.in_tr:
            self.in_td=True; self.cell=[]
    def handle_data(self, data):
        if self.in_td: self.cell.append(data)
    def handle_endtag(self, tag):
        tag=tag.lower()
        if tag=="td" and self.in_td:
            v=" ".join("".join(self.cell).split())
            self.row.append(html.unescape(v)); self.in_td=False
        elif tag=="tr" and self.in_tr:
            if self.row: self.rows.append(self.row)
            self.in_tr=False

def fetch(url):
    req=urllib.request.Request(url, headers={
        "User-Agent":"Mozilla/5.0 (compatible; BakiyeQuoteRefresh/1.0)",
        "Accept":"text/html,application/xhtml+xml",
        "Accept-Language":"tr-TR,tr;q=0.9",
        "Cache-Control":"no-cache",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8","ignore")

def number(s):
    s=re.sub(r"[^0-9,.-]","",s or "").strip()
    if not s: return None
    if "," in s: s=s.replace(".","").replace(",",".")
    try: return float(s)
    except: return None

def parse_stock(source):
    p=TableParser(); p.feed(source)
    out={}
    for symbol in STOCKS:
        for row in p.rows:
            cells=[x.strip().upper() for x in row]
            if symbol in cells:
                i=cells.index(symbol)
                if i+1 < len(row):
                    v=number(row[i+1])
                    if v is not None:
                        out[symbol]=v; break
    # fallback against stripped text if the site changes table markup
    plain=re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",source))
    for symbol in STOCKS:
        if symbol in out: continue
        m=re.search(r"(?:^|\s)"+re.escape(symbol)+r"\s+([0-9]+(?:[.,][0-9]+)?)",plain,re.I)
        if m: out[symbol]=number(m.group(1))
    return out

def main():
    path="/tmp/quotes.json"
    with open(path,encoding="utf-8") as f: q=json.load(f)
    source=fetch(STOCK_SOURCE)
    prices=parse_stock(source)
    missing=[s for s in STOCKS if s not in prices]
    if missing:
        raise SystemExit("Uzmanpara parse failed; missing: "+",".join(missing))
    q["source"]="Uzmanpara Son fiyat (15 dk gecikmeli) + Döviz.com serbest piyasa"
    q["sourceUrl"]=STOCK_SOURCE
    q["asOf"]=datetime.now(timezone.utc).date().isoformat()
    q["lastRefresh"]=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
    q["quotes"].update(prices)
    q["missing"]=missing
    q["errors"]=[]
    q["sourceStatus"]={"uzmanpara":"fulfilled","refreshMethod":"GitHub Actions direct fetch"}
    with open(path,"w",encoding="utf-8") as f: json.dump(q,f,ensure_ascii=False,indent=2)
    print("source:",q["source"])
    print("lastRefresh:",q["lastRefresh"])
    print("quotes:",q["quotes"])
    print("missing:",q["missing"])
    print("errors:",q["errors"])

if __name__=="__main__":
    main()
