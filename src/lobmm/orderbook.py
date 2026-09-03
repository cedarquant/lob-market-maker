from __future__ import annotations

from collections import defaultdict, deque
from decimal import Decimal

from .models import Order, OrderType, Side, Trade


class LimitOrderBook:
    """Deterministic price-time-priority continuous matching engine."""

    def __init__(self, tick_size: Decimal | str = "0.01") -> None:
        self.tick_size = Decimal(tick_size)
        if self.tick_size <= 0:
            raise ValueError("tick_size must be positive")
        self._bids: dict[Decimal, deque[Order]] = defaultdict(deque)
        self._asks: dict[Decimal, deque[Order]] = defaultdict(deque)
        self._orders: dict[str, Order] = {}
        self._clock = 0
        self._trade_sequence = 0

    @property
    def best_bid(self) -> Decimal | None:
        return max(self._bids, default=None)

    @property
    def best_ask(self) -> Decimal | None:
        return min(self._asks, default=None)

    @property
    def mid_price(self) -> Decimal | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return (self.best_bid + self.best_ask) / 2

    @property
    def spread(self) -> Decimal | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return self.best_ask - self.best_bid

    def submit(self, order: Order) -> list[Trade]:
        if order.order_id in self._orders:
            raise ValueError(f"duplicate order id: {order.order_id}")
        self._validate_tick(order)
        self._clock += 1
        order.timestamp = self._clock
        trades = self._match(order)
        if order.remaining and order.order_type is OrderType.LIMIT:
            book = self._bids if order.side is Side.BUY else self._asks
            book[order.price].append(order)  # type: ignore[index]
            self._orders[order.order_id] = order
        return trades

    def cancel(self, order_id: str) -> bool:
        order = self._orders.pop(order_id, None)
        if order is None:
            return False
        book = self._bids if order.side is Side.BUY else self._asks
        level = book[order.price]  # type: ignore[index]
        book[order.price] = deque(item for item in level if item.order_id != order_id)  # type: ignore[index]
        if not book[order.price]:  # type: ignore[index]
            del book[order.price]  # type: ignore[index]
        return True

    def depth(self, side: Side, levels: int | None = None) -> list[tuple[Decimal, int]]:
        book = self._bids if side is Side.BUY else self._asks
        prices = sorted(book, reverse=side is Side.BUY)
        result = [(price, sum(order.remaining for order in book[price])) for price in prices]
        return result[:levels] if levels is not None else result

    def order(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    def _match(self, taker: Order) -> list[Trade]:
        opposite = self._asks if taker.side is Side.BUY else self._bids
        trades: list[Trade] = []
        while taker.remaining and opposite:
            best_price = min(opposite) if taker.side is Side.BUY else max(opposite)
            if taker.order_type is OrderType.LIMIT and not self._crosses(taker, best_price):
                break
            level = opposite[best_price]
            maker = level[0]
            quantity = min(taker.remaining, maker.remaining)
            taker.remaining -= quantity
            maker.remaining -= quantity
            self._trade_sequence += 1
            trades.append(
                Trade(
                    trade_id=self._trade_sequence,
                    timestamp=self._clock,
                    price=best_price,
                    quantity=quantity,
                    aggressor_side=taker.side,
                    maker_order_id=maker.order_id,
                    taker_order_id=taker.order_id,
                    maker_participant_id=maker.participant_id,
                    taker_participant_id=taker.participant_id,
                )
            )
            if maker.remaining == 0:
                level.popleft()
                self._orders.pop(maker.order_id, None)
            if not level:
                del opposite[best_price]
        return trades

    @staticmethod
    def _crosses(order: Order, best_opposite: Decimal) -> bool:
        if order.side is Side.BUY:
            return order.price >= best_opposite  # type: ignore[operator]
        return order.price <= best_opposite  # type: ignore[operator]

    def _validate_tick(self, order: Order) -> None:
        if order.price is not None:
            ticks = order.price / self.tick_size
            if ticks != ticks.to_integral_value():
                raise ValueError(f"price {order.price} is not aligned to tick {self.tick_size}")
