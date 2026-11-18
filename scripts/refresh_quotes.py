import json, re, html, urllib.request, time
from datetime import datetime, timezone

FX_SOURCE = "https://kur.doviz.com/"
GOLD_API = "https://api.gramhane.com/v1/prices.json"
FXC = ["USD","EUR","GBP"]
STOCKS = ["TAVHL","KARSN","THYAO","CGCAM","SISE","ZPLIB.F"]
SOURCE_SYMBOL = {"ZPLIB.F":"ZPLIB"}

# Stock page URLs are kept in one data file so they can be replaced without
# touching the quote engine. Missing URLs are intentionally not guessed.
SOURCES_FILE = "data/stock-sources.json"

def fetch(url, retries=3):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
    }
    last_err = None
    for attempt in range(1, retries + 1):
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
    s = re.sub(r"[^0-9,.-]", "", s or "").strip()
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except:
        return None

def clean_html(source):
    source = html.unescape(source or "")
    source = re.sub(r"<script[\s\S]*?</script>", " ", source, flags=re.I)
    source = re.sub(r"<style[\s\S]*?</style>", " ", source, flags=re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", source)).strip()

def parse_oyak_stock(source, symbol):
    # Prefer a row/cell containing the ticker, then take the first numeric
    # value after it. If the page is card-based, fall back to the "Son" label.
    decoded = html.unescape(source or "")
    rows = re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", decoded, flags=re.I)
    for row_html in rows:
        cells = [clean_html(x) for x in re.findall(r"<t[dh][^>]*>([\s\S]*?)</t[dh]>", row_html, flags=re.I)]
        cells = [x for x in cells if x]
        if any(x.upper() == symbol.upper() for x in cells):
            i = next(i for i,x in enumerate(cells) if x.upper() == symbol.upper())
            for candidate in cells[i+1:]:
                v = number(candidate)
                if v is not None and v > 0:
                    return v, None

    text = clean_html(decoded)
    patterns = [
        rf"\b{re.escape(symbol)}\b\s+([0-9]+(?:[.,][0-9]+)?)",
        r"\bSon\b\s*[:：]?\s*([0-9]+(?:[.,][0-9]+)?)",
        r"\bSon Fiyat\b\s*[:：]?\s*([0-9]+(?:[.,][0-9]+)?)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            v = number(m.group(1))
            if v is not None and v > 0:
                tm = re.search(r"\b(\d{2}:\d{2}:\d{2})\b", text)
                return v, tm.group(1) if tm else None
    return None, None

def parse_fx(source):
    text = clean_html(source)
    out = {}
    for code in FXC:
        m = re.search(rf"\b{re.escape(code)}\b[^0-9]{{1,80}}([0-9]+(?:[.,][0-9]+)?)", text, re.I)
        if m:
            v = number(m.group(1))
            if v is not None:
                out[code + "TRY"] = v
    return out

def main():
    with open("/tmp/quotes.json", encoding="utf-8") as f:
        q = json.load(f)

    with open(SOURCES_FILE, encoding="utf-8") as f:
        source_config = json.load(f)

    pages = source_config.get("stocks", {})
    prices, quote_times, missing, errors = {}, {}, [], []

    for symbol in STOCKS:
        url = pages.get(symbol)
        if not url:
            missing.append(symbol)
            errors.append(f"OYAK URL eksik: {symbol}")
            continue
        try:
            source = fetch(url)
            price, quote_time = parse_oyak_stock(source, SOURCE_SYMBOL.get(symbol, symbol))
            if price is None:
                missing.append(symbol)
                errors.append(f"OYAK fiyatı ayrıştırılamadı: {symbol}")
            else:
                prices[symbol] = price
                if quote_time:
                    quote_times[symbol] = quote_time
        except Exception as exc:
            missing.append(symbol)
            errors.append(f"OYAK {symbol}: {exc}")

    if len(prices) != len(STOCKS):
        raise SystemExit("OYAK fiyatları eksik: " + ",".join(missing))

    fx_source = fetch(FX_SOURCE)
    fx = parse_fx(fx_source)
    fx_missing = [c + "TRY" for c in FXC if c + "TRY" not in fx]
    if fx_missing:
        raise SystemExit("Döviz.com parse failed; missing: " + ",".join(fx_missing))

    gold_api_source = fetch(GOLD_API)
    gold_json = json.loads(gold_api_source)
    if gold_json.get("meta", {}).get("status") != "success":
        raise SystemExit("Gramhane altın verisi başarılı değil")
    gold_rates = gold_json.get("kurlar", {})
    gold_record = gold_rates.get("ALTIN") or gold_rates.get("GRAM") or {}
    gold_gram_try = number(str(gold_record.get("satis") or gold_record.get("alis") or ""))
    if gold_gram_try is None or gold_gram_try <= 1000:
        raise SystemExit("Gramhane Gram Altın satış fiyatı eksik/geçersiz")

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    q["source"] = "OYAK Yatırım hisse sayfaları + Döviz.com serbest piyasa"
    q["sourceUrl"] = "OYAK Yatırım"
    q["stockSourceUrls"] = pages
    q["asOf"] = now[:10]
    q["lastRefresh"] = now
    q["quotes"].update(prices)
    q["quoteTimes"] = {**q.get("quoteTimes", {}), **quote_times}
    q["dailyPct"] = q.get("dailyPct", {})
    q["fx"].update(fx)
    q["goldGramTRY"] = round(gold_gram_try, 2)
    q["goldSource"] = GOLD_API
    q["missing"] = []
    q["errors"] = []
    q["sourceStatus"] = {"oyak": "fulfilled", "doviz": "fulfilled", "refreshMethod": "GitHub Actions direct fetch · individual OYAK pages"}

    with open("/tmp/quotes.json", "w", encoding="utf-8") as f:
        json.dump(q, f, ensure_ascii=False, indent=2)

    print("source:", q["source"])
    print("lastRefresh:", q["lastRefresh"])
    print("quotes:", q["quotes"])

if __name__ == "__main__":
    main()
