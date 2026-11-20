#!/usr/bin/env python3
"""
Lekka Market Agent
------------------
Runs on GitHub Actions every hour (free). No Claude, no paid API.
Fetches: Nifty 50, Sensex, India VIX, gold, silver, Brent crude, USD/INR
Writes:  data/market.json  (read by the Lekka app on your phone)
         data/history.csv  (one row per day, for trends)

India gold/silver price = international price x USD/INR x India premium
(import duty + GST). Default premium 1.09 — change GOLD_PREMIUM in the
workflow if duty changes. The app also self-calibrates when you type the
real jeweller/broker rate once.
"""
import json, os, sys, time, csv, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))
OUT = os.path.join(os.path.dirname(__file__), "..", "data")
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) LekkaAgent/1.0"}
PREMIUM = float(os.environ.get("GOLD_PREMIUM", "1.09"))
OZ = 31.1035

SYMBOLS = {
    "nifty":  "^NSEI",
    "sensex": "^BSESN",
    "vix":    "^INDIAVIX",
    "goldUsd":  "GC=F",
    "silverUsd": "SI=F",
    "brent":  "BZ=F",
    "usdinr": "INR=X",
}


def get_json(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # network hiccup → retry
            if i == tries - 1:
                print(f"  ! {url[:70]}… failed: {e}", file=sys.stderr)
            time.sleep(2 * (i + 1))
    return None


def yahoo(sym):
    """1 year of daily closes from Yahoo's public chart endpoint."""
    q = urllib.request.quote(sym)
    for host in ("query1", "query2"):
        d = get_json(f"https://{host}.finance.yahoo.com/v8/finance/chart/{q}?range=1y&interval=1d")
        try:
            res = d["chart"]["result"][0]
            closes = [c for c in res["indicators"]["quote"][0]["close"] if c is not None]
            meta = res["meta"]
            last = meta.get("regularMarketPrice") or closes[-1]
            prev = meta.get("chartPreviousClose") if len(closes) < 2 else closes[-2]
            return {"last": last, "prev": prev, "closes": closes}
        except Exception:
            continue
    return None


def fallback_fx():
    d = get_json("https://open.er-api.com/v6/latest/USD")
    try:
        return {"last": d["rates"]["INR"], "prev": d["rates"]["INR"], "closes": [d["rates"]["INR"]]}
    except Exception:
        return None


def fallback_metal(code):
    d = get_json(f"https://api.gold-api.com/price/{code}")
    try:
        return {"last": d["price"], "prev": d["price"], "closes": [d["price"]]}
    except Exception:
        return None


def stats(s, scale=1.0):
    closes = [c * scale for c in s["closes"]] or [s["last"] * scale]
    last, prev = s["last"] * scale, (s["prev"] or s["last"]) * scale
    hi, lo = max(closes + [last]), min(closes + [last])
    return {
        "last": round(last, 2), "prev": round(prev, 2),
        "chgPct": round((last - prev) / prev * 100, 2) if prev else 0.0,
        "high52": round(hi, 2), "low52": round(lo, 2),
        "offHighPct": round((last - hi) / hi * 100, 2) if hi else 0.0,
        "chg30Pct": round((last - closes[-22]) / closes[-22] * 100, 2) if len(closes) > 22 else None,
    }


def build_alerts(m):
    """Market-level alerts. The app adds personal ones (your budget, your gold average)."""
    A = []
    def add(i, lvl, title, body):
        A.append({"id": f"{i}-{datetime.now(IST).strftime('%Y%m%d')}", "level": lvl, "title": title, "body": body})
    n = m.get("nifty")
    if n:
        if n["chgPct"] <= -2:
            add("nifty-drop", "warn", f"Nifty fell {abs(n['chgPct']):.1f}% today",
                "Don't sell in panic. SIPs continue as planned.")
        if n["offHighPct"] <= -10:
            add("nifty-correction", "tip", f"Nifty {abs(n['offHighPct']):.0f}% below its 1-year high",
                "Your rule: after a >10% fall, move 1 extra month of SIP from the debt bucket into the Nifty index fund.")
        if n["chgPct"] >= 2:
            add("nifty-jump", "tip", f"Nifty up {n['chgPct']:.1f}% today", "Don't chase. Stick to the monthly SIP.")
    g = m.get("gold")
    if g and abs(g["chgPct"]) >= 2.5:
        add("gold-move", "warn" if g["chgPct"] > 0 else "tip",
            f"Gold {'jumped' if g['chgPct'] > 0 else 'fell'} {abs(g['chgPct']):.1f}% today",
            "Keep buying only your monthly gold SIP. No lumpsum.")
    b = m.get("brent")
    if b:
        if b["last"] >= 110:
            add("oil-high", "bad", f"Brent crude ${b['last']:.0f}", "Oil shock: inflation and rupee risk. Keep SIPs, keep debt short, avoid new loans.")
        elif b["last"] <= 85:
            add("oil-low", "good", f"Brent crude ${b['last']:.0f}", "Lower oil helps India: inflation, rupee and stocks. No change to your plan.")
    fx = m.get("usdinr")
    if fx and abs(fx["chgPct"]) >= 0.8:
        add("inr-move", "warn", f"Rupee moved {fx['chgPct']:+.1f}% vs USD (₹{fx['last']:.2f})",
            "Imported items (phones, electronics) price changes follow. Your gold/silver SIP is the rupee hedge.")
    v = m.get("vix")
    if v and v["last"] >= 20:
        add("vix-high", "warn", f"India VIX at {v['last']:.1f} — high fear",
            "Expect big daily swings. Do nothing new; SIPs only.")
    return A


def main():
    os.makedirs(OUT, exist_ok=True)
    raw = {}
    for k, s in SYMBOLS.items():
        print(f"fetch {k} ({s})")
        raw[k] = yahoo(s)
    if not raw.get("usdinr"):
        raw["usdinr"] = fallback_fx()
    if not raw.get("goldUsd"):
        raw["goldUsd"] = fallback_metal("XAU")
    if not raw.get("silverUsd"):
        raw["silverUsd"] = fallback_metal("XAG")

    m = {}
    for k in ("nifty", "sensex", "vix", "brent", "usdinr"):
        if raw.get(k):
            m[k] = stats(raw[k])
    fx = raw.get("usdinr")
    if fx and raw.get("goldUsd"):
        # ₹ per 10 g, 24K, India estimate. Use 1-year FX path ≈ last FX (good enough for highs).
        m["gold"] = stats(raw["goldUsd"], fx["last"] / OZ * 10 * PREMIUM)
        m["gold"]["usdOz"] = round(raw["goldUsd"]["last"], 2)
    if fx and raw.get("silverUsd"):
        m["silver"] = stats(raw["silverUsd"], fx["last"] / OZ * 1000 * PREMIUM)
        m["silver"]["usdOz"] = round(raw["silverUsd"]["last"], 2)

    if not m:
        print("No data fetched — keeping previous market.json", file=sys.stderr)
        return 0

    out = {
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "updatedIST": datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST"),
        "premium": PREMIUM,
        "market": m,
        "alerts": build_alerts(m),
        "note": "Gold/silver = international price × USD/INR × India duty+GST factor (estimate). Jeweller rates differ by city and making charges.",
    }
    with open(os.path.join(OUT, "market.json"), "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)

    # daily history row (one per IST date)
    hp = os.path.join(OUT, "history.csv")
    today = datetime.now(IST).strftime("%Y-%m-%d")
    rows = []
    if os.path.exists(hp):
        with open(hp) as f:
            rows = [r for r in csv.reader(f)]
    head = ["date", "nifty", "sensex", "gold10g", "silverKg", "brent", "usdinr", "vix"]
    rows = [r for r in rows if r and r[0] != today and r[0] != "date"]
    g = lambda k: m.get(k, {}).get("last", "")
    rows.append([today, g("nifty"), g("sensex"), g("gold"), g("silver"), g("brent"), g("usdinr"), g("vix")])
    with open(hp, "w", newline="") as f:
        w = csv.writer(f); w.writerow(head); w.writerows(rows[-1500:])
    print("market.json written:", ", ".join(f"{k}={v['last']}" for k, v in m.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
