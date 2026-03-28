"""
example_trader.py — Minimal Prosperity trader demonstrating dashboard-compatible logging.

This file shows the minimum structure needed to produce .log files that work
with the visualizer. The Logger class serialises TradingState into the compact
JSON format that parser.js expects. Copy it into your own trader and call
logger.flush() at the end of every run() call.

The Trader class below implements a trivially simple strategy (buy/sell at the
best bid-1 / best ask+1) purely to illustrate the pattern — it has no edge.
Replace the body of run() with your own logic.
"""

import json
from datamodel import (
    Order, OrderDepth, TradingState, Listing, Trade, Observation,
    ProsperityEncoder, Symbol,
)
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Logger — produces the compressed JSON format that parser.js can read.
# Copy this class verbatim into your own trader.
# ─────────────────────────────────────────────────────────────────────────────

class Logger:
    def __init__(self) -> None:
        self.logs: str = ""
        self.max_log_length: int = 7500

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        log_line = sep.join(map(str, objects)) + end
        if len(self.logs) + len(log_line) < self.max_log_length - 500:
            self.logs += log_line
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
        return [[t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp]
                for arr in trades.values() for t in arr] if trades else []

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
# Example Trader — replace this with your own strategy.
# This implementation has no edge; it simply places passive quotes one tick
# inside the best bid/ask as a structural example.
# ─────────────────────────────────────────────────────────────────────────────

POSITION_LIMIT = 20   # conservative limit for the example


class Trader:
    def run(self, state: TradingState) -> tuple[dict[Symbol, list[Order]], int, str]:
        orders: dict[Symbol, list[Order]] = {}

        for symbol, depth in state.order_depths.items():
            if not depth.buy_orders or not depth.sell_orders:
                continue

            best_bid = max(depth.buy_orders.keys())
            best_ask = min(depth.sell_orders.keys())
            current_pos = state.position.get(symbol, 0)

            symbol_orders: list[Order] = []

            # Passive buy one tick inside best bid (no edge, just structure demo)
            buy_price = best_bid - 1
            buy_qty   = min(5, POSITION_LIMIT - current_pos)
            if buy_qty > 0:
                symbol_orders.append(Order(symbol, buy_price, buy_qty))

            # Passive sell one tick inside best ask
            sell_price = best_ask + 1
            sell_qty   = min(5, POSITION_LIMIT + current_pos)
            if sell_qty > 0:
                symbol_orders.append(Order(symbol, sell_price, -sell_qty))

            if symbol_orders:
                orders[symbol] = symbol_orders

        trader_data = ""  # persist state across ticks via this string if needed
        conversions  = 0

        logger.flush(state, orders, conversions, trader_data)
        return orders, conversions, trader_data
