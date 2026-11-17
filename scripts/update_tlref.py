#!/usr/bin/env python3
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TV_URL = "https://tr.tradingview.com/symbols/BIST-TLREF/"
TV_SCAN_URL = "https://scanner.tradingview.com/turkey/scan"
OUT = Path("data/tlref.json")
STOPAJ = 0.175
START_DATE = "2025-08-24"
ISTANBUL = ZoneInfo("Europe/Istanbul")


def tv_tlref():
    # Request the exchange/source timestamp as well as the rate.
    payload = {
        "columns": ["close", "time"],
        "symbols": {"tickers": ["BIST:TLREF"]},
        "range": [0, 1],
    }
    req = urllib.request.Request(
        TV_SCAN_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "text/plain;charset=UTF-8",
            "Accept": "application/json",
            "Origin": "https://www.tradingview.com",
            "Referer": TV_URL,
            "User-Agent": "Mozilla/5.0",
            "Cache-Control": "no-cache",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    for row in data.get("data", []):
        if str(row.get("s", "")).split(":")[-1].upper() != "TLREF":
            continue
        values = row.get("d", [])
        if len(values) < 2 or values[0] is None or values[1] is None:
            raise RuntimeError("TradingView TLREF response has no source timestamp")

        rate_percent = float(values[0])
        source_ts = float(values[1])
        # TradingView's scanner time is normally Unix seconds. Accept ms defensively.
        if source_ts > 10_000_000_000:
            source_ts /= 1000
        source_time = datetime.fromtimestamp(source_ts, tz=timezone.utc)
        source_date = source_time.astimezone(ISTANBUL).date().isoformat()

        if not 20 < rate_percent < 60:
            raise RuntimeError(f"TLREF rate outside valid range: {rate_percent}")

        return rate_percent / 100, source_date, source_time.replace(microsecond=0)

    raise RuntimeError("TradingView BIST:TLREF quote not returned; response=" + json.dumps(data, ensure_ascii=False)[:2500])


now = datetime.now(timezone.utc).replace(microsecond=0)
today = now.astimezone(ISTANBUL).date().isoformat()
rate, source_date, source_time = tv_tlref()

previous = {}
if OUT.exists():
    try:
        previous = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Existing TLREF archive cannot be read safely: {exc}") from exc

historical_map = {
    item["date"]: float(item["rate"])
    for item in previous.get("historical", [])
    if item.get("date") and item.get("rate") is not None
}
previous_as_of = previous.get("asOf")
if previous_as_of:
    previous_rate = previous.get("grossAnnualRate")
    if previous_rate is not None:
        historical_map.setdefault(previous_as_of, float(previous_rate))

latest_existing_date = max(historical_map) if historical_map else None

# Never stamp yesterday's delayed quote with today's date.
if source_date > today:
    raise RuntimeError(
        f"TradingView timestamp is in the future: {source_date}; local date is {today}"
    )

if latest_existing_date and source_date < latest_existing_date:
    raise RuntimeError(
        f"TradingView quote is older than saved TLREF data: "
        f"source={source_date}, saved={latest_existing_date}"
    )

historical_map[source_date] = rate
historical = [
    {"date": date_key, "rate": historical_map[date_key]}
    for date_key in sorted(historical_map)
]
latest = historical[-1]
latest_date = latest["date"]
latest_rate = float(latest["rate"])
net = latest_rate * (1 - STOPAJ)

payload = {
    "source": "TradingView BIST:TLREF",
    "sourceUrl": TV_URL,
    "asOf": latest_date,
    "grossAnnualRate": latest_rate,
    "stopaj": STOPAJ,
    "netAnnualRate": net,
    "startDate": previous.get("startDate", START_DATE),
    "historical": historical,
    "updatedAt": now.isoformat().replace("+00:00", "Z"),
    "sourceTime": source_time.isoformat().replace("+00:00", "Z"),
    "sourceDate": source_date,
    "todayAvailable": latest_date == today,
    "method": (
        "Günlük net TLREF fırsat maliyeti; TradingView BIST:TLREF üzerinden "
        "brüt TLREF, %17,5 stopaj sonrası netleştirilir ve günlük bileşiklenir."
    ),
}
OUT.write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

status = "bugünkü veri doğrulandı" if latest_date == today else "bugünkü oran henüz kaynakta yok; son doğrulanmış veri korundu"
print(
    f"TradingView BIST:TLREF source_date={source_date} "
    f"source_time={payload['sourceTime']} rate={rate * 100:.4f}% "
    f"net={net * 100:.4f}% as_of={latest_date}; {status}; "
    f"{len(historical)} kayıt"
)
