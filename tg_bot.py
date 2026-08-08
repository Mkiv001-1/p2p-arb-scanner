#!/usr/bin/env python3
"""
Telegram bot: monitors P2P arbitrage spreads and alerts when a profitable
opportunity appears. Requires TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID in env.
Deploy on any free host (PythonAnywhere/Render/Railway) or run locally.
"""
import os, json, time, urllib.request, urllib.parse, threading

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "600"))  # seconds
MIN_NET_PCT = float(os.environ.get("MIN_NET_PCT", "2.0"))
STATE_FILE = os.path.join(os.path.dirname(__file__), "bot_state.json")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"}

def tg_send(text):
    if not BOT_TOKEN or not CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": "true"}).encode()
    try:
        req = urllib.request.Request(url, data=data, headers=UA)
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode()).get("ok", False)
    except Exception as e:
        print(f"[tg] send failed: {e}")
        return False

def okx_quotes(fiat, side):
    url = ("https://www.okx.com/v3/c2c/tradingOrders/books"
           f"?quoteCurrency={fiat}&baseCurrency=usdt&side={side}"
           "&userType=all&showTrade=false&showFollow=false&showAlreadyTraded=false&isAbleFilter=false")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read().decode())
    vals = []
    for it in d.get("data", {}).get(side, []):
        try:
            vals.append(float(it["price"]))
        except (TypeError, ValueError, KeyError):
            continue
    if not vals:
        return None
    vals.sort()
    n = len(vals)
    return vals[min(n - 1, 3 * n // 4)] if side == "sell" else vals[max(0, n // 4 - 1)]

def check():
    fiats = ["KZT", "UAH", "TRY", "VND", "NGN", "GEL", "AZN", "KGS", "PLN", "KES"]
    alerts = []
    for f in fiats:
        try:
            buy = okx_quotes(f, "buy")
            sell = okx_quotes(f, "sell")
            if buy and sell:
                spread = (sell - buy) / buy * 100
                net = spread - 1.0
                if net >= MIN_NET_PCT:
                    alerts.append(f"{f}: buy {buy:.2f} / sell {sell:.2f} = {spread:.1f}% (net ~{net:.1f}%)")
        except Exception as e:
            pass
        time.sleep(0.3)
    return alerts

def main():
    if not BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN not set. Monitoring disabled; run check once:")
    while True:
        alerts = check()
        print(f"[{time.strftime('%H:%M')}] checked, {len(alerts)} alerts")
        if alerts and BOT_TOKEN:
            tg_send("🚨 P2P ARB ALERT\n" + "\n".join(alerts))
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
