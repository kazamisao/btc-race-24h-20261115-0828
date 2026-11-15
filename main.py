"""Momentum rider for cbBTC/USDC, 1-minute bars (agent-fun/bars-replay/v1).

Strategy: wait in cash, then ride a strong upward move with the whole stack,
and get out on a short trailing stop. Long only, at most one open position.

Entry (flat only), on a bar's close:
  A) the 20-bar return is above +150 bps, or
  B) the 15-bar return is above +90 bps AND the 30-bar return is above +80 bps
     (a sustained move, not a one-bar spike).
  Either leg means the same thing: price has moved up hard and kept moving.

Exit (holding only): sell everything when the close falls 50 bps or more
below the highest close seen since the entry (trailing stop on closes).

Why this shape: on 1-minute bars the noise is ~12 bps/min and a full round
trip costs ~26 bps in fees, slippage and impact, so fast crossovers whipsaw
and lose money (EMA-cross baselines lose $45-$225 on the dev window, RSI
mean-reversion loses too). The only durable edge in a 24h window is a
multi-hundred-bps trend leg; this bot waits for one, rides it, and cuts it
short when it turns. Dev window: net PnL +$29.11, 2 trades, max drawdown
0.81% (buy-and-hold on the same window: -$44.01).

Determinism: pure integer arithmetic on the bar closes (bps ratios computed
with //), no randomness, no clock, no network, no file reads. Two runs on
the same bars produce identical replies.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"
# Entry thresholds, in basis points of return over the lookback.
ENTRY_A_LOOKBACK = 20
ENTRY_A_MIN_BPS = 150
ENTRY_B_LOOKBACK = 15
ENTRY_B_MIN_BPS = 90
ENTRY_B_CONFIRM_LOOKBACK = 30
ENTRY_B_CONFIRM_MIN_BPS = 80
# Trailing stop: sell when the close is this far below the peak close.
TRAIL_BPS = 50
# Slippage cap per order vs the latest close (bps). 150 gives room for the
# fast open after a momentum bar without chasing a gap.
MAX_SLIPPAGE_BPS = 150
# A buy must spend at least this (the protocol's min notional, 1 USDC).
MIN_NOTIONAL_QUOTE_UNITS = 1_000_000

closes = []  # CBBTC closes, ints at price_scale 5, oldest first.
peak = None  # Highest close since the entry, while holding.


def log(msg):
    """Diagnostics go to stderr only: stdout carries replies alone."""
    print(msg, file=sys.stderr, flush=True)


def ret_bps(now, then):
    """Return in bps from `then` to `now`, truncated toward -inf (ints only)."""
    return (now - then) * 10000 // then


def on_batch(state, batch):
    global peak
    if state.warming_up:
        return []
    bar = None
    for b in batch["bars"]:
        if b["symbol"] == SYMBOL:
            bar = b
            break
    if bar is None:
        return []  # No new bar for CBBTC this minute: decide nothing.
    close = int(bar["c"])
    closes.append(close)

    held = state.positions.get(SYMBOL)
    if held is not None:
        if peak is None:
            peak = close
        elif close > peak:
            peak = close
        if (peak - close) * 10000 // peak >= TRAIL_BPS:
            peak = None
            log(f"seq {state.seq}: SELL {held.qty} qty, close {close}, "
                f"trailing stop {TRAIL_BPS} bps below peak")
            return [{"side": "sell", "symbol": SYMBOL, "qty": held.qty,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        return []

    peak = None
    n = len(closes)
    enter = False
    if n > ENTRY_A_LOOKBACK:
        if ret_bps(close, closes[-1 - ENTRY_A_LOOKBACK]) > ENTRY_A_MIN_BPS:
            enter = True
    if not enter and n > ENTRY_B_CONFIRM_LOOKBACK:
        if (ret_bps(close, closes[-1 - ENTRY_B_LOOKBACK]) > ENTRY_B_MIN_BPS
                and ret_bps(close, closes[-1 - ENTRY_B_CONFIRM_LOOKBACK])
                > ENTRY_B_CONFIRM_MIN_BPS):
            enter = True
    if enter and state.cash >= MIN_NOTIONAL_QUOTE_UNITS:
        peak = close
        log(f"seq {state.seq}: BUY {state.cash} quote units, close {close}")
        return [{"side": "buy", "symbol": SYMBOL,
                 "notional_quote_units": state.cash,
                 "max_slippage_bps": MAX_SLIPPAGE_BPS}]
    return []


makefun_bars.run(on_batch)
