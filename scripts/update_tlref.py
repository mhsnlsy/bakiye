#!/usr/bin/env python3
import json
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

BIST_URL = "https://www.borsaistanbul.com/endeksler/tlref"
OUT = Path("data/tlref.json")
STOPAJ = 0.175
START_DATE = "2025-08-24"
ISTANBUL = ZoneInfo("Europe/Istanbul")


def parse_rate(text):
    value = text.replace("%", "").replace(chr(160), "").replace(" ", "").strip()
    if "," in value:
        value = value.replace(".", "").replace(",", ".")
    rate = float(value)
    if not 20 < rate < 60:
        raise ValueError(f"TLREF rate outside valid range: {rate}")
    return rate / 100


def fetch_latest_bist_row():
    # The #tlref-data rows are rendered by the page's JavaScript.
    # Use the same selector visible in the live page DOM.
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is not installed in the workflow environment.") from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(locale="tr-TR")
            page.set_default_timeout(30000)
            page.goto(BIST_URL, wait_until="domcontentloaded", timeout=60000)
            rows_locator = page.locator("#tlref-data > tr")
            try:
                rows_locator.first.wait_for(state="attached", timeout=30000)
            except Exception:
                # Keep a fallback in case Borsa İstanbul changes the immediate
                # child level while retaining the same table body ID.
                rows_locator = page.locator("#tlref-data tr")
                rows_locator.first.wait_for(state="attached", timeout=15000)

            rows = rows_locator.evaluate_all(
                "(rows) => rows.map(row => "
                "Array.from(row.querySelectorAll('td')).map(cell => cell.innerText.trim()))"
            )
        finally:
            browser.close()

    parsed = []
    for cells in rows:
        if len(cells) < 2:
            continue
        try:
            row_date = datetime.strptime(cells[0], "%d.%m.%Y").date()
            row_rate = parse_rate(cells[1])
        except (ValueError, TypeError):
            continue
        parsed.append((row_date, row_rate))

    if not parsed:
        raise RuntimeError(
            "The live Borsa İstanbul page loaded, but no date/rate rows were found "
            "under #tlref-data."
        )
    return max(parsed, key=lambda item: item[0])


def main():
    now = datetime.now(timezone.utc).replace(microsecond=0)
    today = now.astimezone(ISTANBUL).date()
    previous = {}
    if OUT.exists():
        try:
            previous = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError(f"Existing TLREF archive cannot be read safely: {exc}") from exc

    history = {
        item["date"]: float(item["rate"])
        for item in previous.get("historical", [])
        if item.get("date") and item.get("rate") is not None
    }
    previous_as_of = previous.get("asOf")
    if previous_as_of and previous.get("grossAnnualRate") is not None:
        history.setdefault(previous_as_of, float(previous["grossAnnualRate"]))
    latest_existing_date = max(history) if history else None

    fetch_warning = None
    try:
        source_date, rate = fetch_latest_bist_row()
        source_date = source_date.isoformat()
        if date.fromisoformat(source_date) > today:
            raise RuntimeError(f"Borsa İstanbul TLREF date is in the future: {source_date}")
        if latest_existing_date and source_date < latest_existing_date:
            fetch_warning = (
                f"Source table is older than saved data ({source_date} < {latest_existing_date}); "
                "saved data retained."
            )
        else:
            history[source_date] = rate
            print(f"Borsa İstanbul TLREF row: {source_date} {rate * 100:.4f}%")
    except Exception as exc:
        fetch_warning = f"Could not refresh from Borsa İstanbul: {exc}; saved data retained."

    if not history:
        raise RuntimeError(fetch_warning or "No TLREF history available.")

    historical = [
        {"date": day, "rate": history[day]}
        for day in sorted(history)
    ]
    latest = historical[-1]
    latest_date = latest["date"]
    latest_rate = float(latest["rate"])
    net = latest_rate * (1 - STOPAJ)

    payload = {
        "source": "Borsa İstanbul TLREF",
        "sourceUrl": BIST_URL,
        "asOf": latest_date,
        "grossAnnualRate": latest_rate,
        "stopaj": STOPAJ,
        "netAnnualRate": net,
        "startDate": previous.get("startDate", START_DATE),
        "historical": historical,
        "updatedAt": previous.get("updatedAt"),
        "fetchedAt": previous.get("fetchedAt"),
        "sourceDateBasis": "Borsa İstanbul TLREF tablosundaki #tlref-data satırının tarihi",
        "sourceDate": latest_date,
        "todayAvailable": latest_date == today.isoformat(),
        "method": (
            "Günlük net TLREF fırsat maliyeti; Borsa İstanbul'un yayımladığı brüt TLREF "
            "%17,5 stopaj sonrası netleştirilir ve günlük bileşiklenir."
        ),
    }

    changed = (
        previous.get("asOf") != latest_date
        or previous.get("grossAnnualRate") != latest_rate
        or previous.get("source") != payload["source"]
        or previous.get("sourceUrl") != BIST_URL
    )
    stamp = now.isoformat().replace("+00:00", "Z")
    payload["updatedAt"] = stamp if changed else (previous.get("updatedAt") or stamp)
    payload["fetchedAt"] = stamp if changed else (previous.get("fetchedAt") or stamp)

    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + chr(10),
        encoding="utf-8",
    )
    status = "today's BIST row confirmed" if payload["todayAvailable"] else "latest saved row retained; today's row not yet available"
    if fetch_warning:
        print("WARNING: " + fetch_warning)
    print(
        f"TLREF source=Borsa İstanbul as_of={latest_date} "
        f"gross={latest_rate * 100:.4f}% net={net * 100:.4f}% "
        f"history={len(historical)} rows; {status}"
    )


if __name__ == "__main__":
    main()
