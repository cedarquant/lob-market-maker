from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"

    @property
    def opposite(self) -> Side:
        return Side.SELL if self is Side.BUY else Side.BUY


class OrderType(str, Enum):
    LIMIT = "limit"
    MARKET = "market"


@dataclass(slots=True)
class Order:
    order_id: str
    participant_id: str
    side: Side
    quantity: int
    order_type: OrderType = OrderType.LIMIT
    price: Decimal | None = None
    timestamp: int = 0
    remaining: int = field(init=False)

    def __post_init__(self) -> None:
        self.remaining = self.quantity
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.order_type is OrderType.LIMIT and self.price is None:
            raise ValueError("limit orders require a price")
        if self.order_type is OrderType.MARKET and self.price is not None:
            raise ValueError("market orders cannot have a price")


@dataclass(frozen=True, slots=True)
class Trade:
    trade_id: int
    timestamp: int
    price: Decimal
    quantity: int
    aggressor_side: Side
    maker_order_id: str
    taker_order_id: str
    maker_participant_id: str
    taker_participant_id: str
