"""Builds stocks/prices.json for the class portfolio tracker.

Reads tickers from stocks/tickers.txt (one per line, # for comments),
pulls about a year of daily closing prices from Yahoo Finance (no API key),
and keeps the previous data for any ticker that fails this run.
Run by .github/workflows/stock-prices.yml.
"""
import json
import pathlib
import sys
from datetime import datetime, timezone

import yfinance as yf

HERE = pathlib.Path(__file__).parent
OUT = HERE / "prices.json"
EXCHANGE_SUFFIXES = {"HK", "TO", "L", "T", "DE", "PA", "AX", "V", "SS", "SZ", "KS", "NS", "BO"}


def norm(raw: str) -> str:
    """Match the tracker's ticker cleanup: uppercase, drop 'NYSE:'-style prefixes."""
    t = raw.strip().upper().replace(" ", "")
    if ":" in t:
        t = t.split(":")[-1]
    return t


def yahoo_symbol(t: str) -> str:
    """BRK.B -> BRK-B for Yahoo, but keep exchange suffixes like 0625.HK."""
    if "." in t and t.rsplit(".", 1)[1] not in EXCHANGE_SUFFIXES:
        return t.replace(".", "-")
    return t


def read_tickers() -> list[str]:
    tickers = {"SPY"}
    for line in (HERE / "tickers.txt").read_text().splitlines():
        line = line.split("#", 1)[0]
        if line.strip():
            tickers.add(norm(line))
    return sorted(tickers)


def fetch(t: str):
    tk = yf.Ticker(yahoo_symbol(t))
    hist = tk.history(period="1y", interval="1d", auto_adjust=False)
    if hist.empty:
        return None
    series = [[d.strftime("%Y-%m-%d"), round(float(c), 4)]
              for d, c in hist["Close"].dropna().items()]
    currency = None
    try:
        currency = tk.fast_info.get("currency")
    except Exception:
        pass
    return {"currency": currency or "USD", "series": series}


def main():
    old = {}
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text()).get("prices", {})
        except Exception:
            old = {}

    prices, failed = {}, []
    for t in read_tickers():
        try:
            data = fetch(t)
        except Exception as e:  # network hiccup, Yahoo throttling, bad symbol
            print(f"{t}: {e}", file=sys.stderr)
            data = None
        if data:
            prices[t] = data
        else:
            failed.append(t)
            if t in old:
                prices[t] = old[t]  # keep yesterday's data rather than losing it

    fetched = len(prices) - sum(1 for t in failed if t in prices)
    print(f"Fetched {fetched}, failed {len(failed)}: {' '.join(failed) or 'none'}")
    if fetched == 0:
        sys.exit("No prices fetched; leaving prices.json unchanged.")

    OUT.write_text(json.dumps({
        "updated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "failed": failed,
        "prices": prices,
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
