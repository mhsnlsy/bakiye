#!/usr/bin/env python3
"""Create one verified daily portfolio snapshot at 18:40 Europe/Istanbul."""
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

API_BASE = "https://bakiye.muhsin-ulusoy.workers.dev"
BALANCE_FILE = Path("data/balance.json")
POSITIONS_FILE = Path("data/positions.json")
TLREF_FILE = Path("data/tlref.json")
HISTORY_FILE = Path("data/history.json")
RETENTION_DAYS = 700
SNAPSHOT_WINDOW_START = (18, 35)
SNAPSHOT_WINDOW_END = (18, 50)


def load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def api_json(path):
    url = f"{API_BASE}{path}?snapshot={int(time.time() * 1000)}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": "Bakiye-Daily-Snapshot/1.0",
        },
    )
    with urlopen(request, timeout=35) as response:
        if response.status != 200:
            raise RuntimeError(f"{path}: HTTP {response.status}")
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, (dict, list)):
        raise RuntimeError(f"{path}: invalid JSON payload")
    return payload


def api_or_file(path, fallback):
    try:
        return api_json(path)
    except Exception as exc:
        print(f"NOTICE: {path} API unavailable; using repository file ({exc})")
        return load_json(fallback)


def parse_timestamp(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def money(value):
    return round(float(value or 0), 2)


def fx_value(accounts, rates, account_id):
    currencies = (accounts.get(account_id) or {}).get("currencies") or {}
    return sum(
        float(amount or 0) * float(rates.get(f"{code}TRY", 0) or 0)
        for code, amount in currencies.items()
    )


def main():
    now = datetime.now(ZoneInfo("Europe/Istanbul"))
    force = os.environ.get("FORCE_SNAPSHOT") == "1"
    within_window = (
        (now.hour, now.minute) >= SNAPSHOT_WINDOW_START
        and (now.hour, now.minute) <= SNAPSHOT_WINDOW_END
    )
    if not force and not within_window:
        raise SystemExit(
            f"Snapshot skipped: local time is {now:%Y-%m-%d %H:%M} Europe/Istanbul; "
            "expected 18:35–18:50."
        )

    today = now.date().isoformat()

    # Quotes must come from the live OYAK-backed Worker API; the repository's
    # data/quotes.json is only a seed file and must never be used for a snapshot.
    quotes_data = api_json("/api/quotes")
    if quotes_data.get("sourceUrl") != "OYAK Yatırım":
        raise SystemExit("Snapshot refused: live quote source is not OYAK Yatırım.")

    quote_attempt = parse_timestamp(quotes_data.get("lastAttempt") or quotes_data.get("lastRefresh"))
    if quote_attempt is None:
        raise SystemExit("Snapshot refused: OYAK API has no valid lastAttempt timestamp.")
    if (datetime.now(quote_attempt.tzinfo) - quote_attempt).total_seconds() > 10 * 60:
        raise SystemExit("Snapshot refused: OYAK quote response is older than 10 minutes.")

    balance = api_or_file("/api/balance", BALANCE_FILE)
    positions = api_or_file("/api/positions", POSITIONS_FILE)
    try:
        tlref = api_json("/api/tlref")
    except Exception as exc:
        print(f"NOTICE: /api/tlref unavailable; using repository file ({exc})")
        tlref = load_json(TLREF_FILE)

    if not isinstance(positions, list) or not positions:
        raise SystemExit("Snapshot refused: positions list is empty.")

    prices = quotes_data.get("quotes") or {}
    statuses = quotes_data.get("quoteStatusBySymbol") or {}
    fetched_at = quotes_data.get("quoteFetchedAt") or {}
    missing = []
    stale = []
    for position in positions:
        symbol = position.get("symbol")
        price = prices.get(symbol)
        if not isinstance(price, (int, float)) or price <= 0:
            missing.append(symbol)
            continue
        status = (statuses.get(symbol) or {}).get("status")
        timestamp = parse_timestamp(fetched_at.get(symbol) or (statuses.get(symbol) or {}).get("fetchedAt"))
        if status and status != "fresh":
            stale.append(symbol)
        elif timestamp is None or (datetime.now(timestamp.tzinfo) - timestamp).total_seconds() > 10 * 60:
            stale.append(symbol)
    if missing:
        raise SystemExit("Snapshot refused; missing live OYAK quotes: " + ", ".join(missing))
    if stale:
        raise SystemExit("Snapshot refused; stale OYAK quotes: " + ", ".join(stale))

    accounts = balance.get("accounts") or {}
    rates = quotes_data.get("fx") or {}

    stocks = 0.0
    funds = 0.0
    nominal_cost_total = 0.0
    real_cost_total = 0.0
    daily_cost_total = 0.0
    daily_cost_ready = True

    for position in positions:
        symbol = position["symbol"]
        quantity = float(position.get("qty", 0) or 0)
        market_value = quantity * float(prices[symbol])
        if position.get("type") == "fund":
            funds += market_value
        else:
            stocks += market_value

        average_cost = float(position.get("avgCost", 0) or 0)
        real_cost = float(position.get("realCost", average_cost) or average_cost)
        nominal_cost_total += average_cost * quantity
        real_cost_total += real_cost * quantity
        daily_cost_total += float(position.get("dailyTlrefCostAdded", 0) or 0) * quantity
        if position.get("dailyTlrefCostUpdatedAt") != today:
            daily_cost_ready = False

    try_value = sum(
        float(account.get("value", 0) or 0)
        for account in accounts.values()
        if account.get("category") == "try"
    )
    cash_fx = fx_value(accounts, rates, "doviz")
    bank_fx = fx_value(accounts, rates, "bankaDoviz")

    gold_account = accounts.get("nkolayAltin") or {}
    gold_grams = float(gold_account.get("grams", 0) or 0)
    gold_price = float(quotes_data.get("goldGramTRY") or 0)
    gold_fetched_at = parse_timestamp(quotes_data.get("goldPriceFetchedAt"))
    gold_is_fresh = quotes_data.get("goldPriceStatus") == "fresh"
    gold_age_seconds = (datetime.now(gold_fetched_at.tzinfo) - gold_fetched_at).total_seconds() if gold_fetched_at else float("inf")
    if gold_grams <= 0 or gold_price <= 0 or not gold_is_fresh or gold_age_seconds > 10 * 60:
        raise SystemExit("Snapshot refused: missing or stale live Gramhane gram-gold buy price or gold grams")
    gold = gold_grams * gold_price

    receivable = sum(
        float(account.get("value", 0) or 0)
        for account in accounts.values()
        if account.get("category") == "receivable"
    )

    components = {
        "stocks": money(stocks),
        "funds": money(funds),
        "try": money(try_value),
        "cashFx": money(cash_fx),
        "bankFx": money(bank_fx),
        "gold": money(gold),
        "receivable": money(receivable),
    }
    total = money(sum(components.values()))
    nominal_cost_total = money(nominal_cost_total)
    real_cost_total = money(real_cost_total)
    cumulative_cost = money(real_cost_total - nominal_cost_total)
    daily_cost = money(daily_cost_total) if daily_cost_ready else 0.0

    snapshot = {
        "date": today,
        "capturedAt": now.isoformat(timespec="seconds"),
        "snapshotTime": "18:40 Europe/Istanbul",
        **components,
        "total": total,
        "realCostTotal": real_cost_total,
        "nominalCostTotal": nominal_cost_total,
        "tlrefCostAdded": daily_cost,
        "tlrefDailyCostAdded": daily_cost,
        "tlrefDailyCostAvailable": daily_cost_ready,
        "tlrefCumulativeCostAdded": cumulative_cost,
        "tlrefAsOf": tlref.get("asOf"),
        "tlrefGrossAnnualRate": tlref.get("grossAnnualRate"),
        "tlrefNetAnnualRate": tlref.get("netAnnualRate"),
        "quoteLastRefresh": quotes_data.get("lastRefresh"),
        "quoteSource": "OYAK Yatırım",
    }

    try:
        history = load_json(HISTORY_FILE)
    except FileNotFoundError:
        history = {
            "version": 1,
            "frequency": "daily",
            "startDate": today,
            "retentionDays": RETENTION_DAYS,
            "snapshots": [],
            "weeklySnapshots": [],
        }

    snapshots = history.get("snapshots") or []
    if any(row.get("date") == today for row in snapshots):
        print(f"Snapshot already exists for {today}; preserving the existing 18:40 record.")
        return

    snapshots.append(snapshot)
    snapshots.sort(key=lambda row: row.get("date", ""))
    cutoff = now.date() - timedelta(days=RETENTION_DAYS - 1)
    snapshots = [
        row for row in snapshots
        if datetime.fromisoformat(row["date"]).date() >= cutoff
    ]
    history["snapshots"] = snapshots[-RETENTION_DAYS:]
    history["retentionDays"] = RETENTION_DAYS
    history["frequency"] = "daily"
    history["startDate"] = history["snapshots"][0]["date"] if history["snapshots"] else today
    history["updatedAt"] = now.isoformat(timespec="seconds")

    if now.weekday() == 6:
        weekly = history.get("weeklySnapshots") or []
        weekly = [row for row in weekly if row.get("date") != today]
        weekly.append(snapshot)
        weekly.sort(key=lambda row: row.get("date", ""))
        history["weeklySnapshots"] = weekly[-RETENTION_DAYS:]

    HISTORY_FILE.write_text(
        json.dumps(history, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"18:40 snapshot saved: {today}; total={total:.2f}; "
        f"stocks={components['stocks']:.2f}; fx={components['cashFx'] + components['bankFx']:.2f}; "
        f"snapshots={len(history['snapshots'])}"
    )


if __name__ == "__main__":
    main()
