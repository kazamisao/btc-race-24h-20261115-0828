# Momentum Rider — cbBTC/USDC 1-minute trading bot

Entry for **btc-race-24h-20261115-0828** — "Race a BTC trading bot live for 24 hours".
Python 3.13, standard library only. Speaks `agent-fun/bars-replay/v1`
(NDJSON on stdin/stdout) via the kit's Python SDK shim, vendored byte-identical
under `vendor/`.

## Strategy

Wait in cash, ride one strong upward leg with the whole stack, cut it short
with a trailing stop. Long only, at most one open position, full-size entries.

**Entry** (flat only), decided on a bar's close, filled at the next bar's open:

- **A)** 20-bar return above **+150 bps**, or
- **B)** 15-bar return above **+90 bps** *and* 30-bar return above **+80 bps**
  (a sustained move, not a one-bar spike).

**Exit** (holding only): sell everything when the close falls **50 bps** or
more below the highest close seen since the entry (trailing stop on closes).

Each order caps slippage at 150 bps vs the latest close.

## Why this shape

On 1-minute bars the noise is ~12 bps/min while a full round trip costs
~26 bps in fees (4 bps), slippage (2 bps) and price impact — so fast
crossovers whipsaw and bleed. On the dev window:

| Strategy | Net PnL | Trades | Max drawdown |
|---|---:|---:|---:|
| Buy-and-hold | −$44.01 | 2 | 7.92% |
| EMA-cross 8/21 (house baseline) | −$134.95 | 63 | 13.65% |
| EMA-cross 21/55 | −$45.36 | 24 | 4.77% |
| Donchian 60/10 | +$2.29 | 12 | 1.94% |
| RSI-Bollinger mean reversion | −$46.36 | 10 | 5.87% |
| Momentum 15m >150 bps, hold | +$12.14 | 2 | 2.60% |
| **Momentum rider (this bot)** | **+$29.11** | **2** | **0.81%** |

The dev day's only durable edge is its one big V-recovery rally
(~$62.3k → ~$65.3k in hours 17–18). This bot buys into it at bar 1057
(~$63,087) once the move is confirmed and exits at bar 1137 (~$64,975)
on the trailing stop. Parameter plateau is wide: 20-bar thresholds
140–170 bps with a 50–60 bps trailing stop all score +$23.85…+$24.59,
and the two-leg entry scores +$29.11 — the result is not tuned to one bar.

The rule is direction-agnostic (it buys strength wherever it appears) and
defensive by construction: on a day with no strong up-move it simply stays
in cash. Worst case on a false signal is roughly the trailing stop plus
round-trip costs (~76 bps of the stake).

## Local grade (dev window, 1,440 bars)

Run with the kit's exact fill model (validated against the real harness:
my simulator reproduces the house EMA-cross baseline's official
`grade-local` score, −$134.953038, to the cent) and by driving the real
`main.py` through the protocol twice:

- **Net PnL: +$29.114326 USDC** (start $1,000 → $1,029.11)
- **Trades: 2** (1 buy + 1 sell; the end-of-window flatten is not needed —
  the position was already closed)
- **Fees paid: $0.811811**
- **Max drawdown: 0.81%** (guardrail: ≤ 25%)
- **Guardrails: met** (≥ 1 trade, drawdown well inside the limit)
- **Determinism: verified** — two full runs produce byte-identical action
  logs (same sha256), 1,440 replies each, no crash, no protocol violation.

Note: `grade-local --driver process` cannot run Python bots (Node only) and
no Docker engine is available on this machine, so the official
`grade-local` command could not execute `main.py` here. The numbers above
come from the same fill math, verified against the official grader on the
house baseline as described. The parent should re-run `grade-local`
(official, Docker driver) before submitting.

## Files

- `main.py` — the bot (entrypoint).
- `vendor/makefun_bars.py` — byte-identical copy of the kit's Python SDK shim.
- `LICENSE` — MIT (written by `makefun init`).
- `.makefun/freshness.json` — drand anchor from `makefun init`.

## Determinism

Pure integer arithmetic on bar closes (bps ratios with `//`), no randomness,
no wall clock, no network, no file reads outside the repo. Diagnostics go
to stderr only; stdout carries replies alone.
