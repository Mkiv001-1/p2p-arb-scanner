#!/usr/bin/env python3
"""
P2P Arbitrage Scanner — Bybit + OKX (Binance blocked in jurisdiction).
Finds intra-exchange BUY vs SELL spreads + cross-exchange arb across fiats.
Robust MAD outlier filter. Reports net spread after ~1% fees.
"""
import json, time, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
FIATS = ["RUB", "KZT", "UAH", "TRY", "VND", "BYN", "GEL", "AZN", "KGS", "AMD",
         "KES", "TZS", "PLN", "EUR", "USD", "NGN", "INR", "BRL", "ARS"]

# ── Bybit ──────────────────────────────────────────────────────
def bybit_p2p(fiat, side, token="USDT", rows=10):
    """side: '0' = BUY USDT (lowest wins), '1' = SELL USDT (highest wins)"""
    body = {
        "userId": "", "tokenId": token, "currencyId": fiat,
        "payment": [], "side": side, "size": str(rows), "page": "1",
        "amount": "", "authMaker": False, "canTrade": False,
    }
    req = urllib.request.Request("https://api2.bybit.com/fiat/otc/item/online",
        data=json.dumps(body).encode(),
        headers={**UA, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read().decode())
    except Exception:
        return []
    items = []
    for item in d.get("result", {}).get("items", []):
        try:
            items.append({
                "price": float(item["price"]),
                "amount": float(item.get("quantity", 0)),
            })
        except (TypeError, ValueError, KeyError):
            continue
    return items

# ── OKX ─────────────────────────────────────────────────────────
def okx_p2p(fiat, side):
    """side: 'buy' = buy USDT, 'sell' = sell USDT"""
    url = ("https://www.okx.com/v3/c2c/tradingOrders/books"
           f"?quoteCurrency={fiat}&baseCurrency=usdt&side={side}"
           "&userType=all&showTrade=false&showFollow=false&showAlreadyTraded=false&isAbleFilter=false")
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15) as r:
            d = json.loads(r.read().decode())
    except Exception:
        return []
    items = []
    for item in d.get("data", {}).get(side, []):
        try:
            items.append({
                "price": float(item.get("price")),
                "amount": float(item.get("availableAmount", 0)),
            })
        except (TypeError, ValueError):
            continue
    return items

# ── Robust best ─────────────────────────────────────────────────
def robust_best(prices, want="min"):
    """MAD filter: drop ads >3 median abs dev, then percentile pick (25th/75th)."""
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
            kept = [p for p in prices if abs(p["price"] - median) <= 3 * mad]
            if len(kept) >= 2:
                prices = kept
                vals = sorted(p["price"] for p in prices)
                n = len(vals)
    idx = max(0, int(n * 0.25)) if want == "min" else min(n - 1, int(n * 0.75))
    target = vals[idx]
    candidates = sorted(prices, key=lambda p: abs(p["price"] - target))
    for c in candidates:
        if c["amount"] >= 50:
            return c
    return candidates[0]


def main():
    print(f"=== P2P ARBITRAGE SCAN (Bybit + OKX) {time.strftime('%Y-%m-%d %H:%M')} ===")
    print(f"{'FIAT':<5} {'Bybit BUY':>11} {'Bybit SELL':>12} {'OKX BUY':>9} {'OKX SELL':>10} | SPREAD")
    print("-" * 95)

    results = []
    for fiat in FIATS:
        bb = bybit_p2p(fiat, "0", rows=10)  # BUY
        time.sleep(0.25)
        bs = bybit_p2p(fiat, "1", rows=10)  # SELL
        time.sleep(0.25)
        ob = okx_p2p(fiat, "buy")
        time.sleep(0.25)
        os_ = okx_p2p(fiat, "sell")
        time.sleep(0.25)

        bb_best = robust_best(bb, "min")
        bs_best = robust_best(bs, "max")
        ob_best = robust_best(ob, "min")
        os_best = robust_best(os_, "max")

        line = f"{fiat:<5}"
        line += f" {bb_best['price']:>10.2f}" if bb_best else f" {'N/A':>10}"
        line += f" {bs_best['price']:>11.2f}" if bs_best else f" {'N/A':>11}"
        line += f" {ob_best['price']:>8.2f}" if ob_best else f" {'N/A':>8}"
        line += f" {os_best['price']:>9.2f}" if os_best else f" {'N/A':>9}"

        row = {"fiat": fiat}
        # All BUY prices from both exchanges
        all_buy = []
        all_sell = []
        if bb_best: all_buy.append(("Bybit", bb_best))
        if ob_best: all_buy.append(("OKX", ob_best))
        if bs_best: all_sell.append(("Bybit", bs_best))
        if os_best: all_sell.append(("OKX", os_best))

        if all_buy and all_sell:
            buy_ex, buy_p = min(all_buy, key=lambda t: t[1]["price"])
            sell_ex, sell_p = max(all_sell, key=lambda t: t[1]["price"])
            spread = (sell_p["price"] - buy_p["price"]) / buy_p["price"] * 100
            net = spread - 1.0
            flag = " <== ARB!" if net > 1.5 else ""
            line += f" | {buy_ex}→{sell_ex} {spread:+.2f}% net~{net:+.2f}%{flag}"
            row["xarb"] = {"buy_ex": buy_ex, "sell_ex": sell_ex,
                           "spread_pct": round(spread, 2), "net_pct": round(net, 2)}
        print(line)
        results.append(row)

    with open("scan_result.json", "w") as f:
        json.dump({"time": time.time(), "exchanges": ["Bybit", "OKX"], "results": results}, f, indent=2)
    print("\nSaved to scan_result.json")


if __name__ == "__main__":
    main()
