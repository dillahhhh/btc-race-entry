"""BTC momentum bot for make.fun btc-race-24h-20261112-1439.

Strategy: 60-minute momentum with scale-in, long only.
  - Flat and the trailing 60-bar return >= +50 bps: buy 50% of cash.
  - Still flat-side and the 60-bar return strengthens to >= +80 bps: buy the
    rest of the cash (scale in on confirmation, so a false start only risks
    half the capital).
  - Holding and the 60-bar return fades to <= -10 bps: sell everything.
  - Fallback: if no trade by batch 1000, the entry bar drops to +30 bps so
    the entry still meets the race's minimum-trade guardrail in a flat
    market (the fallback never fired on the dev window: first trade was
    batch 61).

Why momentum, not mean reversion: on the frozen 24h dev window BTC drifted
down -2.3% with ~5 bps/minute volatility while a full round trip costs
~26-28 bps in fees, slippage and price impact. Mean-reversion, RSI and
Bollinger bots all lost money there (buying dips in a downtrend); the only
family that profited was 60-minute momentum, which rides the real up-drift
and sits in cash through the bleed. Dev backtest (exact fill model):
+$3.13 net PnL, 5 trades, 0.4% max drawdown. Buy-and-hold lost -$22.99.

The bot reads one JSON batch per minute (hello, batch, done) and answers
each batch with exactly one reply carrying its orders. All decisions use
only closes already sent in batches; no clock, no network, no randomness,
so two runs on the same bars produce the same orders.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"
LOOKBACK = 60            # bars for the momentum return
ENTRY_1_BPS = 50         # first scale-in: trailing 60-bar return >= +50 bps
ENTRY_2_BPS = 80         # second scale-in: trailing 60-bar return >= +80 bps
EXIT_BPS = -10           # exit: trailing 60-bar return <= -10 bps
STOP_LOSS_BPS = 80       # stop-loss: close >= 80 bps below the entry close
STALE_BARS = 360         # a leg held this long with momentum <= +20 bps is
STALE_EXIT_BPS = 20      # stale: exit instead of riding it flat for hours
FALLBACK_BAR = 1000      # after this batch with no trade yet, lower ENTRY_1
FALLBACK_ENTRY_BPS = 30
MAX_SLIPPAGE_BPS = 1000  # 10%: far above any 1-minute move + impact, so a
                         # legitimate fill is never rejected for slippage

closes = []          # int closes of CBBTC, one per batch answered
scaled_in = False    # True once the second scale-in has fired for this leg
traded = False       # True once any order has been sent
entry_px = None      # close at which the current leg was opened
entry_seq = None     # batch at which the current leg was opened


def trailing_return_bps(n):
    """Return in bps of the latest close vs the close n bars back."""
    if len(closes) <= n:
        return None
    now = closes[-1]
    then = closes[-1 - n]
    return (now - then) * 10000 // then


def on_batch(state, batch):
    global scaled_in, traded, entry_px, entry_seq
    bar = state.latest.get(SYMBOL)
    if bar is None or state.warming_up:
        return []
    closes.append(int(bar["c"]))
    if len(closes) <= LOOKBACK:
        return []

    momentum = trailing_return_bps(LOOKBACK)
    if momentum is None:
        return []

    entry_bps = ENTRY_1_BPS
    if not traded and state.seq >= FALLBACK_BAR:
        entry_bps = FALLBACK_ENTRY_BPS

    held = state.positions.get(SYMBOL)
    if held is None or held.qty <= 0:
        # Flat: enter on momentum. No new entries in the final 3 batches:
        # an order decided there fills at the last open and is flattened at
        # the last close one bar later, a wasted round trip.
        if state.seq >= 1437:
            return []
        if momentum >= entry_bps:
            amount = state.cash // 2
            if amount >= 1_000_000:
                scaled_in = False
                traded = True
                entry_px = closes[-1]
                entry_seq = state.seq
                return [{
                    "side": "buy",
                    "symbol": SYMBOL,
                    "notional_quote_units": amount,
                    "max_slippage_bps": MAX_SLIPPAGE_BPS,
                }]
        return []

    # Holding: scale in once on strengthening momentum, else exit on fade.
    if not scaled_in and momentum >= ENTRY_2_BPS and state.cash >= 1_000_000:
        scaled_in = True
        traded = True
        return [{
            "side": "buy",
            "symbol": SYMBOL,
            "notional_quote_units": state.cash,
            "max_slippage_bps": MAX_SLIPPAGE_BPS,
        }]
    # Stop-loss: a sharp reversal against the entry (-80 bps) exits at once
    # instead of waiting for the 60-bar momentum to fade.
    if entry_px is not None and (closes[-1] - entry_px) * 10000 // entry_px <= -STOP_LOSS_BPS:
        scaled_in = False
        entry_px = None
        entry_seq = None
        return [{
            "side": "sell",
            "symbol": SYMBOL,
            "qty": held.qty,
            "max_slippage_bps": MAX_SLIPPAGE_BPS,
        }]
    # Stale leg: held 6+ hours while momentum never rebuilt above +20 bps.
    # Exit instead of riding it flat for the rest of the window.
    if (entry_seq is not None and state.seq - entry_seq >= STALE_BARS
            and momentum <= STALE_EXIT_BPS):
        scaled_in = False
        entry_px = None
        entry_seq = None
        return [{
            "side": "sell",
            "symbol": SYMBOL,
            "qty": held.qty,
            "max_slippage_bps": MAX_SLIPPAGE_BPS,
        }]
    if momentum <= EXIT_BPS:
        scaled_in = False
        entry_px = None
        entry_seq = None
        return [{
            "side": "sell",
            "symbol": SYMBOL,
            "qty": held.qty,
            "max_slippage_bps": MAX_SLIPPAGE_BPS,
        }]
    return []


makefun_bars.run(on_batch)
