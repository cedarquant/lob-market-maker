from __future__ import annotations

import csv
import json
import random
from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from .models import Order, OrderType, Side
from .orderbook import LimitOrderBook
from .strategy import InventoryAwareMarketMaker


@dataclass(frozen=True, slots=True)
class Snapshot:
    step: int
    fundamental: float
    mid: float
    spread: float
    bid_depth: int
    ask_depth: int
    inventory: int
    cash: float
    pnl: float
    trades: int


@dataclass(frozen=True, slots=True)
class SimulationResult:
    snapshots: list[Snapshot]
    total_trades: int
    maker_fills: int
    final_inventory: int
    final_pnl: float
    max_abs_inventory: int


class MarketSimulation:
    def __init__(self, steps: int = 1_000, seed: int = 7, tick_size: str = "0.01") -> None:
        if steps <= 0:
            raise ValueError("steps must be positive")
        self.steps = steps
        self.rng = random.Random(seed)
        self.tick = Decimal(tick_size)
        self.book = LimitOrderBook(self.tick)
        self.maker = InventoryAwareMarketMaker()
        self.fundamental = Decimal("100.00")
        self._sequence = 0

    def run(self) -> SimulationResult:
        snapshots: list[Snapshot] = []
        total_trades = 0
        maker_fills = 0
        live_orders: list[str] = []
        for step in range(self.steps):
            for order_id in live_orders:
                self.book.cancel(order_id)
            live_orders = []
            shock = Decimal(str(self.rng.gauss(0, 0.06)))
            self.fundamental = self._tick_price(max(Decimal(1), self.fundamental + shock))
            live_orders.extend(self._supply_background_liquidity(step))
            mid = self.book.mid_price or self.fundamental
            bid, ask = self.maker.quotes(mid, self.tick, step / self.steps)
            for side, price in ((Side.BUY, bid), (Side.SELL, ask)):
                size = self.maker.allowed_size(side)
                if size:
                    order = self._order("mm", self.maker.participant_id, side, size, OrderType.LIMIT, price)
                    self.book.submit(order)
                    if order.remaining:
                        live_orders.append(order.order_id)
            if self.rng.random() < 0.72:
                side = Side.BUY if self.rng.random() < 0.5 else Side.SELL
                quantity = self.rng.randint(1, 18)
                taker = self._order("flow", "noise-trader", side, quantity, OrderType.MARKET)
                trades = self.book.submit(taker)
                total_trades += len(trades)
                for trade in trades:
                    if self.maker.participant_id in (trade.maker_participant_id, trade.taker_participant_id):
                        self.maker.process_trade(trade)
                        maker_fills += 1
            mid = self.book.mid_price or self.fundamental
            snapshots.append(
                Snapshot(
                    step=step,
                    fundamental=float(self.fundamental),
                    mid=float(mid),
                    spread=float(self.book.spread or 0),
                    bid_depth=sum(q for _, q in self.book.depth(Side.BUY, 5)),
                    ask_depth=sum(q for _, q in self.book.depth(Side.SELL, 5)),
                    inventory=self.maker.inventory,
                    cash=float(self.maker.cash),
                    pnl=float(self.maker.mark_to_market(mid)),
                    trades=total_trades,
                )
            )
        return SimulationResult(
            snapshots=snapshots,
            total_trades=total_trades,
            maker_fills=maker_fills,
            final_inventory=self.maker.inventory,
            final_pnl=snapshots[-1].pnl,
            max_abs_inventory=max(abs(row.inventory) for row in snapshots),
        )

    def _supply_background_liquidity(self, step: int) -> list[str]:
        order_ids: list[str] = []
        half_spread = Decimal("0.80")
        for level in range(4):
            offset = half_spread + Decimal(level) * Decimal("0.25")
            quantity = 30 + level * 10
            for side, price in (
                (Side.BUY, self._tick_price(self.fundamental - offset)),
                (Side.SELL, self._tick_price(self.fundamental + offset)),
            ):
                order = self._order(f"bg-{step}", "background", side, quantity, OrderType.LIMIT, price)
                self.book.submit(order)
                order_ids.append(order.order_id)
        return order_ids

    def _order(
        self,
        prefix: str,
        participant: str,
        side: Side,
        quantity: int,
        order_type: OrderType,
        price: Decimal | None = None,
    ) -> Order:
        self._sequence += 1
        return Order(f"{prefix}-{self._sequence}", participant, side, quantity, order_type, price)

    def _tick_price(self, value: Decimal) -> Decimal:
        return (value / self.tick).to_integral_value(rounding=ROUND_HALF_UP) * self.tick


def save_result(result: SimulationResult, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(asdict(result.snapshots[0])), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(asdict(row) for row in result.snapshots)
    summary = {key: value for key, value in asdict(result).items() if key != "snapshots"}
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    _plot_svg(result, output_dir / "performance.svg")


def _plot_svg(result: SimulationResult, path: Path) -> None:
    """Write a dependency-free SVG chart for portable example output."""
    width, height = 960, 720
    left, right = 90, 25
    panel_height, gap = 175, 45
    rows = result.snapshots
    series = [
        ("Mid price", [r.mid for r in rows], "#2563eb"),
        ("Inventory", [float(r.inventory) for r in rows], "#d97706"),
        ("Mark-to-market PnL", [r.pnl for r in rows], "#059669"),
    ]
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="480" y="30" text-anchor="middle" font-family="sans-serif" font-size="20" font-weight="600">Inventory-aware market maker simulation</text>',
    ]
    chart_width = width - left - right
    for index, (label, values, color) in enumerate(series):
        top = 60 + index * (panel_height + gap)
        low, high = min(values), max(values)
        if high == low:
            high = low + 1
        points = []
        for i, value in enumerate(values):
            x = left + (i / max(1, len(values) - 1)) * chart_width
            y = top + panel_height - ((value - low) / (high - low)) * panel_height
            points.append(f"{x:.1f},{y:.1f}")
        elements.extend(
            [
                f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + panel_height}" stroke="#9ca3af"/>',
                f'<line x1="{left}" y1="{top + panel_height}" x2="{width - right}" y2="{top + panel_height}" stroke="#9ca3af"/>',
                f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="1.5"/>',
                f'<text x="{left - 12}" y="{top + panel_height / 2}" text-anchor="middle" transform="rotate(-90 {left - 12} {top + panel_height / 2})" font-family="sans-serif" font-size="13">{label}</text>',
                f'<text x="{left - 8}" y="{top + 5}" text-anchor="end" font-family="monospace" font-size="11">{high:.2f}</text>',
                f'<text x="{left - 8}" y="{top + panel_height}" text-anchor="end" font-family="monospace" font-size="11">{low:.2f}</text>',
            ]
        )
    elements.append('<text x="480" y="705" text-anchor="middle" font-family="sans-serif" font-size="13">Simulation step</text>')
    elements.append("</svg>")
    path.write_text("\n".join(elements) + "\n", encoding="utf-8")
