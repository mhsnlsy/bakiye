#!/usr/bin/env python3
import json
import urllib.request
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

BIST_URL = "https://www.borsaistanbul.com/endeksler/tlref"
OUT = Path("data/tlref.json")
STOPAJ = 0.175
START_DATE = "2025-08-24"
ISTANBUL = ZoneInfo("Europe/Istanbul")


class TLREFTableParser(HTMLParser):
    """Read the live rows under the page's #tlref-data table body."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.target_tag = None
        self.target_depth = 0
        self.rows = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        attributes = {key.lower(): value for key, value in attrs}
        if self.target_depth == 0:
            if attributes.get("id") == "tlref-data":
                self.target_tag = tag.lower()
                self.target_depth = 1
            return

        tag = tag.lower()
        if tag == self.target_tag:
            self.target_depth += 1
        elif tag == "tr":
            self.row = []
        elif tag == "td" and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if self.target_depth == 0:
            return
        tag = tag.lower()
        if tag == "td" and self.cell is not None and self.row is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.row:
                self.rows.append(self.row)
            self.row = None

        if tag == self.target_tag:
            self.target_depth -= 1
            if self.target_depth == 0:
                self.target_tag = None


def parse_rate(text):
    value = text.replace("%", "").replace("\\xa0", "").replace(" ", "").strip()
    if "," in value:
        value = value.replace(".", "").replace(",", ".")
    rate = float(value)
    if not 20 < rate < 60:
        raise ValueError(f"TLREF rate outside valid range: {rate}")
    return rate / 100


def fetch_latest_bist_row():
    request = urllib.request.Request(
        BIST_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        html = response.read().decode(charset, errors="replace")

    parser = TLREFTableParser()
    parser.feed(html)
    parsed = []
    for cells in parser.rows:
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
            "Borsa İstanbul page did not expose rows under #tlref-data; "
            "the page may have changed or the table may be client-rendered."
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
    if changed:
        payload["updatedAt"] = now.isoformat().replace("+00:00", "Z")
        payload["fetchedAt"] = now.isoformat().replace("+00:00", "Z")
    else:
        payload["updatedAt"] = previous.get("updatedAt") or now.isoformat().replace("+00:00", "Z")
        payload["fetchedAt"] = previous.get("fetchedAt") or payload["updatedAt"]

    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
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
