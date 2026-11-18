import json, re, html, os, sys, urllib.request
from html.parser import HTMLParser
from datetime import datetime, timezone

STOCK_SOURCE = "https://uzmanpara.milliyet.com.tr/canli-borsa/bist-TUM-hisseleri/"
STOCKS = ["TAVHL","KARSN","THYAO","CGCAM","SISE","ZPLIB.F"]
SOURCE_SYMBOL = {"ZPLIB.F":"ZPLIB"}
FX_SOURCE = "https://kur.doviz.com/"
FXC = ["USD","EUR","GBP"]
GOLD_SOURCE = "https://www.doviz.com/"

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

def fetch(url, retries=3):
    import time
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
    }
    last_err = None
    for attempt in range(1, retries+1):
        try:
            req = urllib.request.Request(url + ("&" if "?" in url else "?") + "_ts=" + str(int(datetime.now(timezone.utc).timestamp()*1000)), headers=headers)
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:
            last_err = e
            print(f"Fetch attempt {attempt}/{retries} failed for {url}: {e}")
            if attempt < retries:
                time.sleep(1.5 * attempt)
    raise last_err

def number(s):
    s=re.sub(r"[^0-9,.-]","",s or "").strip()
    if not s: return None
    if "," in s: s=s.replace(".","").replace(",",".")
    try: return float(s)
    except: return None

def parse_gold(source):
    # Doviz.com sayfası fiyat verisini farklı HTML/JSON payload'larında
    # sunabiliyor. Etiketle aynı blok içinde yer alan ilk gerçek fiyatı ara.
    decoded=html.unescape(source)
    plain=re.sub(r"\\s+"," ",re.sub(r"<[^>]+>"," ",decoded))
    patterns=[
        r"Gram\\s*Altın.{0,180}?(?:₺|TL)?\\s*([0-9]{1,3}(?:\\.[0-9]{3})*(?:,[0-9]+)?|[0-9]+(?:[.,][0-9]+)?)",
        r"Gram\\s*Altın.{0,180}?(?:buy|sell|alis|satis|price)[^0-9]{0,30}([0-9]+(?:[.,][0-9]+)?)",
        r"(?:gram-altin|gram_altin|gramAltin|gramGold).{0,160}?(?:buy|sell|alis|satis|price|value)[^0-9]{0,30}([0-9]+(?:[.,][0-9]+)?)",
    ]
    for pattern in patterns:
        m=re.search(pattern,plain,re.I)
        if m:
            v=number(m.group(1))
            if v is not None and v>1000:
                return v

    # JSON-LD / embedded Next/Nuxt JSON: locate a named gold record.
    for label in [r"Gram Altın",r"gram-altin",r"gram_altin",r"gramAltin"]:
        m=re.search(label,decoded,re.I)
        if not m: continue
        chunk=decoded[m.start():m.start()+1200]
        nums=re.findall(r"(?:buy|sell|alis|satis|price|value)[^0-9]{0,30}([0-9]+(?:[.,][0-9]+)?)",chunk,re.I)
        for raw in nums:
            v=number(raw)
            if v is not None and v>1000:
                return v

    # Tablo satırı fallback.
    p=TableParser(); p.feed(decoded)
    for row in p.rows:
        cells=[x.strip() for x in row]
        for i,cell in enumerate(cells):
            if re.search(r"Gram\\s*Altın",cell,re.I):
                for candidate in row[i+1:i+4]:
                    v=number(candidate)
                    if v is not None and v>1000:
                        return v
    return None

def parse_fx(source):
    p=TableParser(); p.feed(source)
    out={}
    for code in FXC:
        for row in p.rows:
            cells=[x.strip().upper() for x in row]
            for i,cell in enumerate(cells):
                if cell.startswith(code+" ") and i+1 < len(row):
                    v=number(row[i+1])
                    if v is not None:
                        out[code+"TRY"]=v
                        break
            if code+"TRY" in out:
                break
    plain=re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",source))
    for code in FXC:
        if code+"TRY" in out: continue
        m=re.search(r"(?:^|\s)"+re.escape(code)+r"(?:\s+[^|]{0,50})?\s*\|\s*([0-9]+(?:[.,][0-9]+)?)",plain,re.I)
        if m: out[code+"TRY"]=number(m.group(1))
    return out

def parse_stock(source):
    p=TableParser(); p.feed(source)
    out={}
    daily_pct={}
    for symbol in STOCKS:
        for row in p.rows:
            cells=[x.strip().upper() for x in row]
            source_symbol=SOURCE_SYMBOL.get(symbol,symbol)
            if source_symbol in cells:
                i=cells.index(source_symbol)
                if i+1 < len(row):
                    v=number(row[i+1])
                    if v is not None:
                        out[symbol]=v
                        if i+2 < len(row):
                            pct=number(row[i+2])
                            if pct is not None: daily_pct[symbol]=pct
                        break
    plain=re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",source))
    for symbol in STOCKS:
        if symbol in out: continue
        source_symbol=SOURCE_SYMBOL.get(symbol,symbol)
        m=re.search(r"(?:^|\s)"+re.escape(source_symbol)+r"\s+([0-9]+(?:[.,][0-9]+)?)",plain,re.I)
        if m: out[symbol]=number(m.group(1))
    return out, daily_pct

def main():
    path="/tmp/quotes.json"
    with open(path,encoding="utf-8") as f: q=json.load(f)
    source=fetch(STOCK_SOURCE)
    prices, daily_pct=parse_stock(source)
    missing=[s for s in STOCKS if s not in prices]
    if missing:
        raise SystemExit("Uzmanpara parse failed; missing: "+",".join(missing))
    fx_source=fetch(FX_SOURCE)
    fx=parse_fx(fx_source)
    gold_gram_try=parse_gold(fx_source)
    if gold_gram_try is None or gold_gram_try <= 0:
        raise SystemExit("Döviz.com parse failed; missing Gram Altın")
    fx_missing=[c for c in FXC if c+"TRY" not in fx]
    if fx_missing:
        raise SystemExit("D\u00f6viz.com parse failed; missing: "+",".join(fx_missing)+"TRY")
    q["source"]="Uzmanpara Son fiyat (15 dk gecikmeli) + D\u00f6viz.com serbest piyasa"
    q["sourceUrl"]=STOCK_SOURCE
    q["asOf"]=datetime.now(timezone.utc).date().isoformat()
    q["lastRefresh"]=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
    q["quotes"].update(prices)
    q["dailyPct"]=daily_pct
    q["fx"].update(fx)
    q["goldGramTRY"] = round(gold_gram_try, 2)
    q["goldSource"] = GOLD_SOURCE
    q["missing"]=missing
    q["errors"]=[]
    q["sourceStatus"]={"uzmanpara":"fulfilled","doviz":"fulfilled","refreshMethod":"GitHub Actions direct fetch"}
    with open(path,"w",encoding="utf-8") as f: json.dump(q,f,ensure_ascii=False,indent=2)
    print("source:",q["source"])
    print("lastRefresh:",q["lastRefresh"])
    print("quotes:",q["quotes"])
    print("goldGramTRY:",q["goldGramTRY"])
    print("missing:",q["missing"])
    print("errors:",q["errors"])

if __name__=="__main__":
    main()
