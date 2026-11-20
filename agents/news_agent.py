#!/usr/bin/env python3
"""
Lekka News & Geo-politics Agent
-------------------------------
Runs on GitHub Actions every 3 hours (free). No Claude, no paid API.
Reads public Google News RSS for the topics that move YOUR money,
tags each headline with what it means for your plan, and writes
data/news.json for the app.
"""
import json, os, re, sys, time, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

IST = timezone(timedelta(hours=5, minutes=30))
OUT = os.path.join(os.path.dirname(__file__), "..", "data")
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) LekkaAgent/1.0"}

# topic → (search query, icon, what it means, your rule)
TOPICS = {
    "rbi":   ("RBI repo rate OR monetary policy India", "🏦",
              "RBI decisions change FD, loan and bond-fund returns.",
              "Rates rising → keep debt short (FD ladder, short-duration fund). Rates cut → longer-duration debt becomes attractive."),
    "oil":   ("crude oil Brent OR Hormuz OR OPEC", "🛢️",
              "Oil is India's largest import: it drives inflation, rupee and markets.",
              "Oil > $110 → don't stop SIPs, avoid new loans. Oil < $85 → no change, enjoy lower inflation."),
    "gold":  ("gold price India today", "🥇",
              "Gold is your crisis hedge, not a growth engine.",
              "Buy only the monthly gold SIP. Rebalance if gold > 20% above your average."),
    "market":("Sensex Nifty today", "📈",
              "Daily market moves are noise for a 10+ year SIP investor.",
              "Rebalance every 6 months. After a >10% fall, add 1 extra month of SIP."),
    "ipo":   ("IPO opens subscription India", "🚀",
              "New IPOs: many are offers-for-sale by existing owners.",
              "Max 5% of portfolio. Read the RHP; ignore grey-market (GMP) hype."),
    "geo":   ("geopolitical tensions markets India", "🌍",
              "Wars, sanctions and tariffs hit oil, rupee and FII flows.",
              "Never react within 48 hours. Your plan already holds gold + debt for shocks."),
    "inr":   ("rupee dollar exchange rate", "₹",
              "A weaker rupee makes imports, foreign travel and gold costlier.",
              "Plan big imported purchases with 'Can I buy?'. Gold SIP is the hedge."),
    "tax":   ("income tax India self-employed OR GST change", "🧾",
              "Tax rule changes can change which regime saves you more.",
              "Note it for your CA; don't change investments only for tax."),
}

BAD = re.compile(r"\b(hike|surge|spike|war|attack|escalat|crash|plunge|slump|fall|tumble|sanction|tariff|default|downgrade|record high inflation)\w*", re.I)
GOOD = re.compile(r"\b(cut|ease|peace|ceasefire|deal|rally|gain|recover|rise in reserves|upgrade|cool)\w*", re.I)


def fetch(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
                return r.read()
        except Exception as e:
            if i == tries - 1:
                print(f"  ! {e}", file=sys.stderr)
            time.sleep(2 * (i + 1))
    return None


def items(query, n=5):
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": query + " when:3d", "hl": "en-IN", "gl": "IN", "ceid": "IN:en"})
    raw = fetch(url)
    if not raw:
        return []
    out = []
    try:
        root = ET.fromstring(raw)
        for it in root.iter("item"):
            title = (it.findtext("title") or "").strip()
            src = (it.findtext("source") or "").strip()
            if src and title.endswith(" - " + src):
                title = title[: -len(src) - 3]
            try:
                dt = parsedate_to_datetime(it.findtext("pubDate")).astimezone(IST)
            except Exception:
                dt = None
            out.append({"title": title, "source": src, "link": it.findtext("link"),
                        "time": dt.isoformat() if dt else None,
                        "tone": "bad" if BAD.search(title) else "good" if GOOD.search(title) else "neutral"})
            if len(out) >= n:
                break
    except ET.ParseError:
        pass
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    topics = []
    for key, (q, icon, means, rule) in TOPICS.items():
        print("news:", key)
        its = items(q)
        tones = [i["tone"] for i in its]
        mood = "bad" if tones.count("bad") >= 3 else "good" if tones.count("good") >= 3 else "mixed"
        topics.append({"key": key, "icon": icon, "means": means, "rule": rule, "mood": mood, "items": its})
    if not any(t["items"] for t in topics):
        print("No news fetched — keeping previous news.json", file=sys.stderr)
        return 0
    out = {"updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "updatedIST": datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST"),
           "topics": topics}
    with open(os.path.join(OUT, "news.json"), "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print("news.json written:", sum(len(t["items"]) for t in topics), "headlines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
