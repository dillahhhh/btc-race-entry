# BTC Momentum Bot — make.fun "Race a BTC trading bot live for 24 hours"

A bot that trades Coinbase Wrapped BTC (cbBTC) against USDC on 1-minute
on-chain prices from its Orca Whirlpool, for
[make.fun/bounty/btc-race-24h-20261112-1439](https://make.fun/bounty/btc-race-24h-20261112-1439).

## Strategy

60-minute momentum with scale-in, long only, $1,000 paper capital:

- **Enter 50%** when the trailing 60-bar return reaches **+50 bps**.
- **Scale in the other 50%** when it strengthens to **+80 bps** (a false
  start only risks half the capital).
- **Exit everything** when the trailing 60-bar return fades to **-10 bps**.
- **Fallback:** if no trade has fired by batch 1000, the entry bar drops to
  +30 bps so the entry still meets the race's minimum-trade guardrail in a
  flat market.
- No new entries in the final 3 batches (an order there would fill at the
  last open and be flattened at the last close one bar later).

## Why momentum

On the frozen 24h dev window BTC drifted down -2.3% with ~5 bps/minute
volatility while a full round trip costs ~26-28 bps in fees, slippage and
price impact. Mean-reversion, RSI and Bollinger bots all lost money there
(buying dips in a downtrend); the only family that profited was 60-minute
momentum, which rides the real up-drift and sits in cash through the bleed.

Dev backtest with the exact fill model (4 bps fee, 2 bps slippage,
constant-product impact against the bar's open depth):

| bot | net PnL | trades | max DD |
|-----|--------:|-------:|-------:|
| this bot | **+$3.13** | 5 | 0.45% |
| buy-and-hold | -$22.99 | 1 | 2.9% |
| best EMA cross | -$17.23 | 26 | 1.8% |
| best RSI | -$17.64 | 10 | 2.1% |
| oracle (perfect foresight) | +$43.41 | 30 | — |

## Run

Python 3.13, standard library only. The entrypoint is `main.py`; it speaks
`agent-fun/bars-replay/v1` (newline-delimited JSON on stdin/stdout) through
the vendored shim `vendor/makefun_bars.py` (a byte-identical copy of the
kit's `sdk/makefun_bars.py`).

```
python3 -P -s main.py
```

All decisions use only closes already sent in batches. No clock, no network,
no files outside the repository, no randomness — two runs on the same bars
produce identical orders.
