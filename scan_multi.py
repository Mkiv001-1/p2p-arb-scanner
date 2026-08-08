#!/usr/bin/env python3
"""
Multi-exchange P2P Arbitrage Scanner (Binance + OKX)
Finds: (1) intra-exchange BUY vs SELL spreads, (2) cross-exchange arb:
buy USDT cheap on OKX P2P, sell on Binance P2P (or vice versa).
All prices in same fiat. Reports net spread after fees (~0.5% assumed).
"""
import json, time, urllib.request, urllib.parse

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}

FIATS = ["RUB", "KZT", "UAH", "TRY", "VND", "BYN", "GEL", "AZN", "KGS", "AMD", "KES", "TZS", "PLN", "EUR", "USD", "NGN"]

def _post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={**UA, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())

def _get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())

def binance_p2p(fiat, trade_type):
    """trade_type: BUY = buying USDT (lowest price wins); SELL = selling USDT (highest wins)"""
    d = _post("https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search",
              {"page": 1, "rows": 5, "payTypes": [], "countries": [], "publisherType": None,
               "asset": "USDT", "fiat": fiat, "tradeType": trade_type})
    prices = []
    for a in d.get("data", []):
        adv = a.get("adv", {})
        prices.append({"price": float(adv["price"]), "amount": float(adv.get("surplusAmount", 0))})
    return prices

def okx_p2p(fiat, side):
    """side: buy = buy USDT; sell = sell USDT"""
    url = ("https://www.okx.com/v3/c2c/tradingOrders/books"
           f"?quoteCurrency={fiat}&baseCurrency=usdt&side={side}"
           "&userType=all&showTrade=false&showFollow=false&showAlreadyTraded=false&isAbleFilter=false")
    d = _get(url)
    prices = []
    for item in d.get("data", {}).get(side, []):
        try:
            prices.append({"price": float(item.get("price")), "amount": float(item.get("availableAmount", 0))})
        except (TypeError, ValueError):
            continue
    return prices

def best(prices, want="min"):
    """Median-anchored quotes: BUY = 25th pct, SELL = 75th pct.
    First drop ads >15% off median (scam/market-maker noise), then percentile."""
    if not prices:
        return None
    vals = sorted(p["price"] for p in prices)
    n = len(vals)
    if n >= 4:
        mid = n // 2
        median = vals[mid] if n % 2 else (vals[mid - 1] + vals[mid]) / 2
        devs = sorted(abs(v - median) for v in vals)
        dm = len(devs) // 2
        mad = devs[dm] if len(devs) % 2 else (devs[dm - 1] + devs[dm]) / 2
        if mad > 0:
            cutoff = 3 * mad
            kept = [p for p in prices if abs(p["price"] - median) <= cutoff]
            if len(kept) >= 2:
                prices = kept
                vals = sorted(p["price"] for p in prices)
                n = len(vals)
    idx = max(0, int(n * 0.25)) if want == "min" else min(n - 1, int(n * 0.75))
    target = vals[idx]
    # pick the ad closest to target percentile with sane volume
    candidates = sorted(prices, key=lambda p: abs(p["price"] - target))
    for c in candidates:
        if c["amount"] >= 50:  # prefer ads with real liquidity
            return c
    return candidates[0]

def main():
    print(f"=== MULTI-EXCHANGE P2P ARBITRAGE SCAN {time.strftime('%Y-%m-%d %H:%M')} ===")
    print("(BUY = price to buy USDT, SELL = price to sell USDT, same fiat)")
    print("-" * 100)
    results = []
    for fiat in FIATS:
        row = {"fiat": fiat}
        try:
            bn_buy = best(binance_p2p(fiat, "BUY"), "min")
            bn_sell = best(binance_p2p(fiat, "SELL"), "max")
        except Exception as e:
            bn_buy = bn_sell = None
        time.sleep(0.3)
        try:
            ok_buy = best(okx_p2p(fiat, "buy"), "min")
            ok_sell = best(okx_p2p(fiat, "sell"), "max")
        except Exception as e:
            ok_buy = ok_sell = None
        time.sleep(0.3)

        line = f"{fiat:<5}"
        if bn_buy: line += f" BN_Buy {bn_buy['price']:>10.2f}"
        if bn_sell: line += f" BN_Sell {bn_sell['price']:>10.2f}"
        if ok_buy: line += f" OK_Buy {ok_buy['price']:>10.2f}"
        if ok_sell: line += f" OK_Sell {ok_sell['price']:>10.2f}"

        # Cross-exchange arb: buy on cheaper, sell on more expensive
        buys = [("BN", bn_buy), ("OK", ok_buy)]
        sells = [("BN", bn_sell), ("OK", ok_sell)]
        buys = [(x, p) for x, p in buys if p]
        sells = [(x, p) for x, p in sells if p]
        if buys and sells:
            buy_x, buy_p = min(buys, key=lambda t: t[1]["price"])
            sell_x, sell_p = max(sells, key=lambda t: t[1]["price"])
            spread = (sell_p["price"] - buy_p["price"]) / buy_p["price"] * 100
            net = spread - 1.0  # fees ~0.5% each side + slippage
            flag = " <== ARB!" if net > 1.0 else ""
            line += f" | X-ARB {buy_x}->{sell_x}: {spread:.2f}% (net~{net:.2f}%){flag}"
            row["xarb"] = {"buy_ex": buy_x, "sell_ex": sell_x, "buy": buy_p["price"],
                           "sell": sell_p["price"], "spread_pct": round(spread, 2), "net_pct": round(net, 2)}
        print(line)
        results.append(row)

    with open("scan_result.json", "w") as f:
        json.dump({"time": time.time(), "results": results}, f, indent=2)
    print("\nSaved to scan_result.json")

if __name__ == "__main__":
    main()
