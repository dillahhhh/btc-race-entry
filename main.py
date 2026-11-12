"""BTC dip-swing bot v2 for make.fun btc-race-24h-20261112-1439.

Strategy: vol-gated dip-swing, long only, $1,000 paper.
  - Flat and the close is >= 46 bps below the trailing 45-bar high AND
    the trailing 30-bar realised volatility (population std of 1-minute
    returns) is >= 5.0 bps: buy 100% of cash.
  - Holding: sell everything when the close is >= +80 bps above the entry
    close (take-profit), <= -50 bps below it (stop-loss), or >= 35 bps
    below the best gain reached since entry (trailing stop).
  - At most 3 round trips per window: extra trips lost money on dev, so
    the bot stops after the third instead of grinding the account down.
  - Fallback: if no trade has happened by batch 1000, the dip bar drops
    to 30 bps and the vol gate is lifted, so the bot still takes at least
    one trade and meets the race guardrail in a flat live window. The
    fallback never fired on the dev window (first trade was batch 45).
  - No new entries in the final 3 batches: an order decided there fills
    at the last open and is flattened at the last close one bar later, a
    wasted round trip.

Why dip-swing, not momentum: on the frozen 24h dev window BTC drifted
down -2.3% with ~5 bps/minute volatility while a full round trip costs
~26 bps in fees, slippage and price impact. The dev leaderboard's top
bots are all vol-gated dip-swings (TP70/SL50 off the 60-bar high); the
60-minute momentum bot (v1) only made +$3.13. This bot buys the sharp
dips at the bottom of the big up-legs and lets the take-profit / trailing
stop bank them. Dev backtest (exact fill model): +$24.57 net PnL,
6 trades (3 round trips), 0.53% max drawdown. Buy-and-hold lost -$22.99.

The bot reads one JSON batch per minute (hello, batch, done) and answers
each batch with exactly one reply carrying its orders. All decisions use
only closes already sent in batches; no clock, no network, no randomness,
so two runs on the same bars produce the same orders.
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"
LOOKBACK = 45            # bars for the dip reference (trailing high)
DIP_BPS = 46             # buy when close is >= 46 bps below the 45-bar high
VOL_WINDOW = 30          # bars for the realised-volatility gate
VOL_MIN_BPS = 5.0        # buy only when 30-bar vol (std of 1m returns) >= 5 bps
TP_BPS = 80              # take-profit: close >= 80 bps above the entry close
SL_BPS = 50              # stop-loss: close <= 50 bps below the entry close
TRAIL_BPS = 35           # trailing stop: close >= 35 bps below the best gain
MAX_RT = 3               # at most 3 round trips per window
FALLBACK_BAR = 1000      # after this batch with no trade yet, relax the entry
FALLBACK_DIP_BPS = 30    # fallback dip bar (vol gate lifted as well)
MAX_SLIPPAGE_BPS = 1000  # 10%: far above any 1-minute move + impact, so a
                         # legitimate fill is never rejected for slippage

closes = []          # int closes of CBBTC, one per batch answered
entry_px = None      # close at which the current leg was opened
peak_ret = None      # best return in bps since entry (for the trailing stop)
round_trips = 0      # completed round trips in this window
traded = False       # True once any order has been sent


def trailing_high_bps():
    """Highest close of the last LOOKBACK bars, including the latest."""
    return max(closes[-LOOKBACK:])


def realised_vol_bps():
    """Population std of the last VOL_WINDOW 1-minute returns, in bps."""
    rets = []
    for j in range(len(closes) - VOL_WINDOW, len(closes)):
        prev = closes[j - 1]
        rets.append((closes[j] - prev) * 10000.0 / prev)
    mean = sum(rets) / len(rets)
    return math.sqrt(sum((r - mean) ** 2 for r in rets) / len(rets))


def on_batch(state, batch):
    global entry_px, peak_ret, round_trips, traded
    bar = state.latest.get(SYMBOL)
    if bar is None or state.warming_up:
        return []
    closes.append(int(bar["c"]))
    if len(closes) <= LOOKBACK:
        return []

    now = closes[-1]
    high = trailing_high_bps()
    dip_bps = DIP_BPS
    vol_min = VOL_MIN_BPS
    if not traded and state.seq >= FALLBACK_BAR:
        dip_bps = FALLBACK_DIP_BPS
        vol_min = 0.0

    held = state.positions.get(SYMBOL)
    if held is None or held.qty <= 0:
        # Flat: enter on a vol-gated dip. No new entries in the final
        # 3 batches, and no entries after the round-trip budget is spent.
        if state.seq >= 1437 or round_trips >= MAX_RT:
            return []
        dip_price = high * (10000 - dip_bps) // 10000
        if now <= dip_price and realised_vol_bps() >= vol_min:
            amount = state.cash
            if amount >= 1_000_000:
                traded = True
                entry_px = now
                peak_ret = -10 ** 9
                return [{
                    "side": "buy",
                    "symbol": SYMBOL,
                    "notional_quote_units": amount,
                    "max_slippage_bps": MAX_SLIPPAGE_BPS,
                }]
        return []

    # Holding: exit on take-profit, stop-loss, or trailing stop.
    ret_e = (now - entry_px) * 10000 // entry_px
    if ret_e > peak_ret:
        peak_ret = ret_e
    if (ret_e >= TP_BPS or ret_e <= -SL_BPS
            or (peak_ret > 0 and ret_e <= peak_ret - TRAIL_BPS)):
        entry_px = None
        peak_ret = None
        round_trips += 1
        return [{
            "side": "sell",
            "symbol": SYMBOL,
            "qty": held.qty,
            "max_slippage_bps": MAX_SLIPPAGE_BPS,
        }]
    return []


makefun_bars.run(on_batch)
