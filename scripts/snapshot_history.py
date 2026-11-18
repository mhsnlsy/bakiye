#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    balance = load("/tmp/balance.json")
    quotes = load("/tmp/quotes.json")
    positions = load("/tmp/positions.json")
    tlref = load("/tmp/tlref.json")

    q = quotes.get("quotes", {})
    rates = quotes.get("fx", {})
    now = datetime.now(timezone.utc)
    today = now.astimezone(ZoneInfo("Europe/Istanbul")).date().isoformat()

    missing = [
        p.get("symbol") for p in positions
        if not isinstance(q.get(p.get("symbol")), (int, float))
        or q.get(p.get("symbol"), 0) <= 0
    ]
    if missing:
        raise SystemExit("Snapshot refused; missing live quotes: " + ", ".join(missing))

    stocks = 0.0
    funds = 0.0
    real_cost_total = 0.0
    nominal_cost_total = 0.0
    daily_cost_total = 0.0
    daily_cost_ready = bool(positions)

    for p in positions:
        symbol = p["symbol"]
        qty = float(p.get("qty", 0) or 0)
        price = float(q[symbol])
        market_value = qty * price
        if p.get("type") == "fund":
            funds += market_value
        else:
            stocks += market_value

        avg_cost = float(p.get("avgCost", 0) or 0)
        real_cost = float(p.get("realCost", avg_cost) or avg_cost)
        nominal_cost_total += avg_cost * qty
        real_cost_total += real_cost * qty

        if p.get("dailyTlrefCostUpdatedAt") != today:
            daily_cost_ready = False
        daily_cost_total += float(p.get("dailyTlrefCostAdded", 0) or 0) * qty

    accounts = balance.get("accounts", {})
    try_value = sum(
        float(x.get("value", 0) or 0)
        for x in accounts.values()
        if x.get("category") == "try"
    )

    def fx_value(account_id):
        currencies = (accounts.get(account_id) or {}).get("currencies") or {}
        return sum(
            float(amount or 0) * float(rates.get(code + "TRY", 0) or 0)
            for code, amount in currencies.items()
        )

    cash_fx = fx_value("doviz")
    bank_fx = fx_value("bankaDoviz")
    gold = sum(
        float(x.get("value", 0) or 0)
        for x in accounts.values()
        if x.get("category") == "gold"
    )
    receivable = sum(
        float(x.get("value", 0) or 0)
        for x in accounts.values()
        if x.get("category") == "receivable"
    )

    components = {
        "stocks": round(stocks, 2),
        "funds": round(funds, 2),
        "try": round(try_value, 2),
        "cashFx": round(cash_fx, 2),
        "bankFx": round(bank_fx, 2),
        "gold": round(gold, 2),
        "receivable": round(receivable, 2),
    }
    total = round(sum(components.values()), 2)
    daily_cost = round(daily_cost_total, 2) if daily_cost_ready else 0.0
    cumulative_cost = round(real_cost_total - nominal_cost_total, 2)

    entry = {
        "date": today,
        "capturedAt": now.isoformat().replace("+00:00", "Z"),
        "snapshotTime": "18:40 Europe/Istanbul",
        **components,
        "total": total,
        "realCostTotal": round(real_cost_total, 2),
        "nominalCostTotal": round(nominal_cost_total, 2),
        "tlrefCostAdded": daily_cost,
        "tlrefDailyCostAdded": daily_cost,
        "tlrefDailyCostAvailable": daily_cost_ready,
        "tlrefCumulativeCostAdded": cumulative_cost,
        "tlrefAsOf": tlref.get("asOf"),
        "tlrefGrossAnnualRate": tlref.get("grossAnnualRate"),
        "tlrefNetAnnualRate": tlref.get("netAnnualRate"),
    }

    try:
        history = load("/tmp/history.json")
    except FileNotFoundError:
        history = {
            "version": 1,
            "frequency": "daily",
            "startDate": today,
            "retentionDays": 700,
            "updatedAt": None,
            "snapshots": [],
        }

    # Aynı gün için zaten başarılı bir 18:40 snapshotı varsa ikinci güvenlik
    # tetikleyicileri mevcut kaydı ezmesin. Böylece gün başına tek gerçek snapshot kalır.
    existing = [s for s in history.get("snapshots", []) if s.get("date") == today]
    if existing:
        print("18:40 snapshot already exists for", today)
        return

    snapshots = [s for s in history.get("snapshots", []) if s.get("date") != today]
    snapshots.append(entry)
    snapshots.sort(key=lambda x: x.get("date", ""))
    history["snapshots"] = snapshots[-700:]
    history["retentionDays"] = 700
    history["updatedAt"] = now.isoformat()
    history["frequency"] = "daily"
    history["snapshotTime"] = "18:40 Europe/Istanbul"
    history["startDate"] = history["snapshots"][0]["date"] if history["snapshots"] else today

    with open("/tmp/history.json", "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    print("18:40 snapshot:", entry)
    print("Component sum:", total)
    print("Snapshots:", len(history["snapshots"]))


if __name__ == "__main__":
    main()
