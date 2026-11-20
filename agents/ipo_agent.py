#!/usr/bin/env python3
"""
Lekka IPO Agent
---------------
Runs on GitHub Actions with the market agent (free). Finds open and upcoming
Indian IPOs, screens each one automatically and writes data/ipo.json.

Sources (in order): NSE public IPO endpoints (needs a cookie handshake; can be
blocked from cloud IPs) → Google News RSS headlines (names, dates, price bands).

The screen is a RULE-BASED FIRST LOOK, not a recommendation:
  • SME issues → AVOID (illiquid, high failure rate)
  • 100% offer-for-sale → no new money for the company (penalty)
  • subscription (once bidding starts) is the strongest public demand signal
  • "listing guess" is a rough range from subscription history — a guess, never a promise
Full review still needs the RHP numbers (Lekka → Grow → 🧰 → IPO Check).
"""
import http.cookiejar, json, os, re, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

IST = timezone(timedelta(hours=5, minutes=30))
OUT = os.path.join(os.path.dirname(__file__), "..", "data")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"


def nse_session():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", UA), ("Accept-Language", "en-IN,en;q=0.9"), ("Accept", "*/*"), ("Referer", "https://www.nseindia.com/market-data/all-upcoming-issues-ipo")]
    op.open("https://www.nseindia.com/", timeout=20).read()
    return op


def nse_issues():
    try:
        op = nse_session()
        cur = json.loads(op.open("https://www.nseindia.com/api/ipo-current-issue", timeout=20).read() or b"[]")
        time.sleep(1)
        up = json.loads(op.open("https://www.nseindia.com/api/all-upcoming-issues?category=ipo", timeout=20).read() or b"[]")
    except Exception as e:  # noqa
        print("  NSE unavailable:", e, file=sys.stderr)
        return []
    out = []
    for status, rows in (("open", cur if isinstance(cur, list) else cur.get("data", [])), ("upcoming", up if isinstance(up, list) else up.get("data", []))):
        for r in rows or []:
            name = r.get("companyName") or r.get("company") or r.get("symbol")
            if not name:
                continue
            band = re.findall(r"[\d.]+", str(r.get("issuePrice") or r.get("priceBand") or ""))
            sub = r.get("noOfTime") or r.get("subscription") or r.get("totalSubscription")
            try:
                sub = float(str(sub).replace("x", "")) if sub not in (None, "", "-") else None
            except ValueError:
                sub = None
            out.append({"name": name.strip(), "symbol": r.get("symbol"), "status": status,
                        "sme": "SME" in str(r.get("series", "")).upper() or "SME" in name.upper(),
                        "open": r.get("issueStartDate"), "close": r.get("issueEndDate"),
                        "price_low": float(band[0]) if band else None, "price_high": float(band[-1]) if band else None,
                        "size_cr": _num(r.get("issueSize")), "subscription": sub, "source": "NSE"})
    return out


def _num(x):
    try:
        v = float(re.sub(r"[^\d.]", "", str(x)))
        return v / 1e7 if v > 1e6 else v      # rupees → crore if given in rupees
    except ValueError:
        return None


NAME_RE = re.compile(r"^([A-Z][\w&.\- ]{2,60}?)\s+IPO\b")
BAND_RE = re.compile(r"(?:Rs\.?|₹)\s?([\d,]+)\s?(?:-|–|to)\s?(?:Rs\.?|₹)?\s?([\d,]+)", re.I)
SUB_RE = re.compile(r"subscribed\s+([\d.]+)\s*(?:x|times)", re.I)


def news_issues():
    q = "IPO opens OR price band OR subscribed mainboard India when:7d"
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"})
    try:
        raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=20).read()
        root = ET.fromstring(raw)
    except Exception as e:  # noqa
        print("  news unavailable:", e, file=sys.stderr)
        return []
    found = {}
    for it in root.iter("item"):
        t = (it.findtext("title") or "").strip()
        m = NAME_RE.search(t)
        if not m:
            continue
        name = m.group(1).strip()
        if name.lower() in ("upcoming", "the", "this week", "sme", "mainboard", "new"):
            continue
        d = found.setdefault(name, {"name": name, "status": "upcoming", "sme": "SME" in t.upper(), "source": "news", "headlines": []})
        b = BAND_RE.search(t)
        if b and not d.get("price_high"):
            d["price_low"], d["price_high"] = float(b.group(1).replace(",", "")), float(b.group(2).replace(",", ""))
        s = SUB_RE.search(t)
        if s:
            d["subscription"] = max(d.get("subscription") or 0, float(s.group(1)))
        if re.search(r"opens today|day \d|subscribed", t, re.I):
            d["status"] = "open"
        try:
            when = parsedate_to_datetime(it.findtext("pubDate")).astimezone(IST).strftime("%d %b")
        except Exception:  # noqa
            when = ""
        if len(d["headlines"]) < 3:
            d["headlines"].append({"title": t, "link": it.findtext("link"), "when": when})
    return list(found.values())[:12]


def screen(x):
    """Rule-based first look. Returns score, verdict, reasons, listing guess."""
    R, s = [], 50
    if x.get("sme"):
        return {"score": 0, "verdict": "AVOID", "reasons": ["SME issue: tiny, illiquid, high risk — not for your plan"], "guess": "not estimated"}
    if x.get("ofs_pct") is not None:
        if x["ofs_pct"] >= 99:
            s -= 10; R.append("100% offer-for-sale: the company gets no new money; existing owners are selling")
        elif x["ofs_pct"] <= 40:
            s += 5; R.append("mostly fresh issue: money goes into the business")
    size = x.get("size_cr")
    if size is not None:
        if size < 150:
            s -= 10; R.append("very small issue (< ₹150 cr)")
        elif size >= 5000:
            R.append("very large issue: listing pop usually smaller")
    sub = x.get("subscription")
    if sub is None:
        R.append("bidding not started / no subscription data yet — the strongest signal is missing")
        guess = "unknown until bids come in"
    else:
        if sub >= 50:
            s += 25; guess = "+15% to +40% (guess)"
        elif sub >= 10:
            s += 15; guess = "0% to +20% (guess)"
        elif sub >= 3:
            s += 5; guess = "−5% to +10% (guess)"
        else:
            s -= 15; guess = "−15% to +5% (guess)"
        R.append("subscribed %.1f× so far" % sub)
    for k in ("psu",):
        if x.get(k):
            R.append("government-owned: steady dividends usually, slower growth")
    v = "CONSIDER (5% bucket only)" if s >= 70 else "OPTIONAL" if s >= 50 else "SKIP"
    return {"score": max(0, min(100, s)), "verdict": v, "reasons": R, "guess": guess}


def main():
    os.makedirs(OUT, exist_ok=True)
    prev = {}
    try:
        prev = {i["name"].lower(): i for i in json.load(open(os.path.join(OUT, "ipo.json")))["ipos"]}
    except Exception:  # noqa
        pass
    items = nse_issues() or news_issues()
    if not items:
        print("No IPO data — keeping previous ipo.json", file=sys.stderr)
        return 0
    out = []
    for x in items:
        old = prev.get(x["name"].lower(), {})
        for k in ("ofs_pct", "psu", "lot", "min_amount", "listing", "valuation_cr", "note"):   # keep curated facts
            if k in old and k not in x:
                x[k] = old[k]
        x.update(screen(x))
        out.append(x)
    out.sort(key=lambda i: (i["status"] != "open", -i["score"]))
    json.dump({"updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "updatedIST": datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST"), "ipos": out,
               "note": "Rule-based first look. Listing guesses are rough ranges from subscription history, not predictions."},
              open(os.path.join(OUT, "ipo.json"), "w"), indent=1, ensure_ascii=False)
    print("ipo.json:", len(out), "issues")
    return 0


if __name__ == "__main__":
    sys.exit(main())
