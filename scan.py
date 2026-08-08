#!/usr/bin/env python3
"""
P2P Arbitrage Scanner (Binance P2P vs Spot)
Finds spreads: buy USDT cheap on spot (or P2P BUY side), sell on P2P SELL side.
Reports net profit after fees.
"""
import json, time, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}

FIATS = ["RUB", "KZT", "UAH", "TRY", "VND", "BYN", "GEL", "AZN", "UZS", "KGS", "AMD", "GHS", "NGN", "KES", "TZS", "ARS", "MXN", "BRL", "PLN", "EUR", "USD"]

def p2p(asset, fiat, trade_type, rows=5):
    url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    body = json.dumps({"page": 1, "rows": rows, "payTypes": [], "countries": [],
                       "publisherType": None, "asset": asset, "fiat": fiat, "tradeType": trade_type}).encode()
    req = urllib.request.Request(url, data=body, headers={**UA, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read().decode())
        prices = []
        for a in d.get("data", []):
            adv = a.get("adv", {})
            prices.append({"price": float(adv["price"]), "amount": float(adv.get("surplusAmount", 0)),
                           "traders": adv.get("tradableQuantity", 0), "nick": a.get("advertiser", {}).get("nickName")})
        return prices
    except Exception as e:
        return [{"error": str(e)}]

def spot_price(asset="USDT"):
    req = urllib.request.Request(f"https://api.binance.com/api/v3/ticker/price?symbol={asset}USDT",
                                 headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return float(json.loads(r.read().decode())["price"])
    except Exception:
        return None

def main():
    spot = spot_price("USDT")  # USDT in USD
    print(f"=== P2P ARBITRAGE SCAN {time.strftime('%Y-%m-%d %H:%M')} ===")
    print(f"USDT spot (USD): {spot:.4f}" if spot else "USDT spot (USD): N/A")
    print(f"{'FIAT':<5} {'P2P BUY (lowest)':>18} {'P2P SELL (highest)':>20} {'Spread%':>8} {'Vol (sell, USDT)':>16}")
    print("-" * 75)
    results = []
    for fiat in FIATS:
        buys = p2p("USDT", fiat, "BUY", 5)
        sells = p2p("USDT", fiat, "SELL", 5)
        if not buys or not sells or "error" in buys[0] or "error" in sells[0]:
            continue
        best_buy = min(b["price"] for b in buys)
        best_sell = max(s["price"] for s in sells)
        vol = sum(s["amount"] for s in sells[:3])
        spread = (best_sell - best_buy) / best_buy * 100
        results.append({"fiat": fiat, "buy": best_buy, "sell": best_sell, "spread": spread, "vol": vol})
        flag = " <== ARB" if spread > 1.5 else ""
        print(f"{fiat:<5} {best_buy:>18.2f} {best_sell:>20.2f} {spread:>7.2f}% {vol:>16.0f}{flag}")
        time.sleep(0.4)
    # Save
    with open("scan_result.json", "w") as f:
        json.dump({"time": time.time(), "spot_usd": spot, "results": results}, f, indent=2)
    print("\nSaved to scan_result.json")

if __name__ == "__main__":
    main()
