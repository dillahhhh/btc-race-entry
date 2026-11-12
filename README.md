# BTC Dip-Swing Bot v2 — make.fun "Race a BTC trading bot live for 24 hours"

A bot that trades Coinbase Wrapped BTC (cbBTC) against USDC on 1-minute
on-chain prices from its Orca Whirlpool, for
[make.fun/bounty/btc-race-24h-20261112-1439](https://make.fun/bounty/btc-race-24h-20261112-1439).

## Strategy

Vol-gated dip-swing, long only, $1,000 paper capital:

- **Enter 100%** when the close is **>= 46 bps below the trailing 45-bar
  high** AND the trailing 30-bar realised volatility (std of 1-minute
  returns) is **>= 5.0 bps** — a violent dip, not a slow bleed.
- **Exit everything** when the close is **>= +80 bps above entry**
  (take-profit), **<= -50 bps below entry** (stop-loss), or **>= 35 bps
  below the best gain since entry** (trailing stop).
- **At most 3 round trips** per window: extra trips lost money on dev.
- **Fallback:** if no trade has fired by batch 1000, the dip bar drops to
  30 bps and the vol gate is lifted, so the entry still meets the race's
  minimum-trade guardrail in a flat market. The fallback never fired on
  the dev window (first trade was batch 45).
- No new entries in the final 3 batches (an order there would fill at the
  last open and be flattened at the last close one bar later).

## Why dip-swing

On the frozen 24h dev window BTC drifted down -2.3% with ~5 bps/minute
volatility while a full round trip costs ~26 bps in fees, slippage and
price impact. The dev leaderboard's top bots are all vol-gated dip-swings
(TP70/SL50 off the 60-bar high); the 60-minute momentum bot (v1) only
made +$3.13. This bot buys the sharp dips at the bottom of the big
up-legs and lets the take-profit / trailing stop bank them.

Dev backtest with the exact fill model (4 bps fee, 2 bps slippage,
constant-product impact against the bar's open depth), verified through
the real bars-replay/v1 wire (2 runs, identical action logs):

| bot | net PnL | trades | max DD |
|-----|--------:|-------:|-------:|
| this bot (v2) | **+$24.57** | 6 (3 RT) | 0.30% |
| v1 momentum | +$3.13 | 5 | 0.45% |
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
