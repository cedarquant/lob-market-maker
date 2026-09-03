from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from .models import Side, Trade


@dataclass(slots=True)
class InventoryAwareMarketMaker:
    """Finite-horizon Avellaneda--Stoikov-inspired quoting policy."""

    participant_id: str = "market-maker"
    risk_aversion: float = 0.12
    volatility: float = 0.25
    liquidity: float = 1.5
    horizon: float = 1.0
    order_size: int = 10
    max_inventory: int = 100
    inventory: int = 0
    cash: Decimal = Decimal(0)

    def quotes(self, mid: Decimal, tick: Decimal, time_fraction: float) -> tuple[Decimal, Decimal]:
        remaining = max(0.0, 1.0 - time_fraction) * self.horizon
        gamma = self.risk_aversion
        sigma2 = self.volatility**2
        reservation = float(mid) - self.inventory * gamma * sigma2 * remaining
        if gamma > 0:
            half_spread = gamma * sigma2 * remaining / 2 + math.log1p(gamma / self.liquidity) / gamma
        else:
            half_spread = 1 / self.liquidity
        bid = self._floor_to_tick(Decimal(str(reservation - half_spread)), tick)
        ask = self._ceil_to_tick(Decimal(str(reservation + half_spread)), tick)
        if ask <= bid:
            ask = bid + tick
        return bid, ask

    def allowed_size(self, side: Side) -> int:
        capacity = self.max_inventory - self.inventory if side is Side.BUY else self.max_inventory + self.inventory
        return max(0, min(self.order_size, capacity))

    def process_trade(self, trade: Trade) -> None:
        notional = trade.price * trade.quantity
        if trade.maker_participant_id == self.participant_id:
            if trade.aggressor_side is Side.BUY:
                self.inventory -= trade.quantity
                self.cash += notional
            else:
                self.inventory += trade.quantity
                self.cash -= notional
        elif trade.taker_participant_id == self.participant_id:
            if trade.aggressor_side is Side.BUY:
                self.inventory += trade.quantity
                self.cash -= notional
            else:
                self.inventory -= trade.quantity
                self.cash += notional

    def mark_to_market(self, mid: Decimal) -> Decimal:
        return self.cash + mid * self.inventory

    @staticmethod
    def _floor_to_tick(value: Decimal, tick: Decimal) -> Decimal:
        return (value / tick).to_integral_value(rounding=ROUND_FLOOR) * tick

    @staticmethod
    def _ceil_to_tick(value: Decimal, tick: Decimal) -> Decimal:
        return (value / tick).to_integral_value(rounding=ROUND_CEILING) * tick
