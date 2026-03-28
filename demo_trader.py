"""
demo_trader.py — Market-making strategy for Prosperity Round 0.

Products:
    EMERALDS  — Extremely stable. Fair value is exactly 10,000 every tick.
                We quote tight spreads at ±8 pts and capture the spread.

    TOMATOES  — Mean-reverting around a fast EMA. We quote at EMA ± edge,
                skewing our quotes against our current position.

Usage:
    prosperity4bt demo_trader.py 0--1 0--2 --merge-pnl --out demo.log

    Or click "Run Backtest" in the visualizer sidebar and select this file.

What this demonstrates:
    - Logger class for full dashboard output (own-trade overlays, PnL chart)
    - SIG line logging to unlock the Microstructure and Imbalance tabs
    - Position-skewed quoting to manage inventory risk
    - Per-product strategy dispatch
"""

import json
from datamodel import (
    Order, OrderDepth, TradingState, Listing, Trade,
    Observation, ProsperityEncoder, Symbol,
)
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Logger — produces the compressed JSON format the visualizer reads.
# Call logger.flush() at the end of every Trader.run() call.
# ─────────────────────────────────────────────────────────────────────────────

class Logger:
    def __init__(self) -> None:
        self.logs: str = ""
        self.max_log_length: int = 7500

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        line = sep.join(map(str, objects)) + end
        if len(self.logs) + len(line) < self.max_log_length - 500:
            self.logs += line
        elif not self.logs.endswith("...\n"):
            self.logs += "...\n"

    def flush(
        self,
        state: TradingState,
        orders: dict[Symbol, list[Order]],
        conversions: int,
        trader_data: str,
    ) -> None:
        print(self.to_json([
            self.compress_state(state, trader_data),
            self.compress_orders(orders),
            conversions,
            trader_data,
            self.logs,
        ]))
        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list[Any]:
        return [
            state.timestamp,
            trader_data,
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations),
        ]

    def compress_listings(self, listings: dict[Symbol, Listing]) -> list[list[Any]]:
        return [[l.symbol, l.product, l.denomination] for l in listings.values()] if listings else []

    def compress_order_depths(self, order_depths: dict[Symbol, OrderDepth]) -> dict[Symbol, list[Any]]:
        return {s: [od.buy_orders or {}, od.sell_orders or {}] for s, od in order_depths.items()} if order_depths else {}

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        return [
            [t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp]
            for arr in trades.values() for t in arr
        ] if trades else []

    def compress_observations(self, observations: Observation) -> list[Any]:
        if not observations:
            return [{}, {}]
        conv = {}
        if hasattr(observations, "conversionObservations") and observations.conversionObservations:
            for p, o in observations.conversionObservations.items():
                conv[p] = [
                    getattr(o, "bidPrice", None), getattr(o, "askPrice", None),
                    getattr(o, "transportFees", None), getattr(o, "exportTariff", None),
                    getattr(o, "importTariff", None),
                ]
        plain = getattr(observations, "plainValueObservations", {}) or {}
        return [plain, conv]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        return [[o.symbol, o.price, o.quantity] for arr in orders.values() for o in arr] if orders else []

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"), default=str)


logger = Logger()

# ─────────────────────────────────────────────────────────────────────────────
# Strategy parameters
# ─────────────────────────────────────────────────────────────────────────────

POSITION_LIMIT  = 20          # max units long or short per product
EMERALDS_FAIR   = 10_000      # hard-coded fair value — never moves
EMERALDS_EDGE   = 8           # quote ±8 pts from fair value
TOMATOES_ALPHA  = 0.08        # EMA decay — smaller = slower / smoother
TOMATOES_EDGE   = 6           # base half-spread for TOMATOES


# ─────────────────────────────────────────────────────────────────────────────
# Trader
# ─────────────────────────────────────────────────────────────────────────────

class Trader:
    """
    Market-maker for EMERALDS and TOMATOES.

    EMERALDS:  fair value is always 10,000.  We sit tight quotes at
               10,000 ± EMERALDS_EDGE and collect the spread.

    TOMATOES:  fair value tracks a fast EMA of the mid-price.  We quote
               at EMA ± TOMATOES_EDGE, then skew the quotes by our
               current inventory so we naturally mean-revert our position.
    """

    def __init__(self) -> None:
        self.ema: dict[str, float] = {}   # per-product EMA of mid-price

    # ── Main entry point ─────────────────────────────────────────────────────

    def run(
        self, state: TradingState
    ) -> tuple[dict[Symbol, list[Order]], int, str]:

        orders: dict[Symbol, list[Order]] = {}

        for sym, depth in state.order_depths.items():
            if not depth.buy_orders or not depth.sell_orders:
                continue

            best_bid = max(depth.buy_orders)
            best_ask = min(depth.sell_orders)
            mid      = (best_bid + best_ask) / 2
            pos      = state.position.get(sym, 0)

            # ── Order Book Imbalance (OBI) ───────────────────────────────────
            bid_vol = sum(depth.buy_orders.values())
            ask_vol = sum(abs(v) for v in depth.sell_orders.values())
            total   = bid_vol + ask_vol
            obi     = (bid_vol - ask_vol) / total if total > 0 else 0.0

            # ── Per-product fair value and edge ─────────────────────────────
            if sym == "EMERALDS":
                fair = float(EMERALDS_FAIR)
                edge = EMERALDS_EDGE

            else:  # TOMATOES and any other trending product
                alpha       = TOMATOES_ALPHA
                prev_ema    = self.ema.get(sym, mid)
                fair        = alpha * mid + (1.0 - alpha) * prev_ema
                self.ema[sym] = fair
                edge        = TOMATOES_EDGE

            # ── Position skew — lean quotes against current inventory ────────
            # If we're long +10 out of +20, skew sell price down by 2 pts so
            # we get hit more often on the sell side and reduce exposure.
            skew       = pos // 4
            buy_price  = round(fair - edge - skew)
            sell_price = round(fair + edge - skew)

            # ── Size — respect position limits ───────────────────────────────
            buy_qty  = min(5, POSITION_LIMIT - pos)
            sell_qty = min(5, POSITION_LIMIT + pos)

            sym_orders: list[Order] = []
            if buy_qty  > 0: sym_orders.append(Order(sym, buy_price,   buy_qty))
            if sell_qty > 0: sym_orders.append(Order(sym, sell_price, -sell_qty))
            if sym_orders:
                orders[sym] = sym_orders

            # ── SIG logging — unlocks Microstructure + Imbalance tabs ────────
            # Format: SIG|PRODUCT|key=value|key=value|...
            # Supported keys: fair_value, bid_wall, ask_wall, ema, obi, tape_vel
            logger.print(
                f"SIG|{sym}"
                f"|fair_value={fair:.1f}"
                f"|bid_wall={buy_price}"
                f"|ask_wall={sell_price}"
                f"|obi={obi:.3f}"
            )

        logger.flush(state, orders, 0, "")
        return orders, 0, ""
