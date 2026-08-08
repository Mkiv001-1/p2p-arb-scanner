# P2P Arbitrage Scanner (Binance + OKX)

Real-time scanner for P2P USDT arbitrage opportunities across Binance and OKX.
Detects intra-exchange (BUY vs SELL) and cross-exchange spreads per fiat currency.

## Usage
```bash
pip install -r requirements.txt  # none needed, stdlib only
python scan_multi.py
```

## Output
- BN_Buy / BN_Sell: Binance P2P quotes (25th/75th percentile, robust vs scam ads)
- OK_Buy / OK_Sell: OKX P2P quotes
- X-ARB: best cross-exchange buy->sell spread (net of ~1% fees)

## Notes
- P2P arbitrage requires KYC-verified accounts + fiat rails on both exchanges.
- Quotes are median-anchored to avoid fake market-maker ads with absurd prices.
- RUB is geo-blocked from some IPs; KZT/UAH/TRY/VND/NGN work well.

Results are saved to scan_result.json.
