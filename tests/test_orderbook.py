from decimal import Decimal

import pytest

from lobmm import LimitOrderBook, Order, OrderType, Side


def limit(order_id: str, side: Side, qty: int, price: str, participant: str = "p") -> Order:
    return Order(order_id, participant, side, qty, OrderType.LIMIT, Decimal(price))


def market(order_id: str, side: Side, qty: int, participant: str = "t") -> Order:
    return Order(order_id, participant, side, qty, OrderType.MARKET)


def test_non_crossing_limit_rests() -> None:
    book = LimitOrderBook()
    assert book.submit(limit("b1", Side.BUY, 5, "99.00")) == []
    assert book.best_bid == Decimal("99.00")
    assert book.depth(Side.BUY) == [(Decimal("99.00"), 5)]


def test_crossing_limit_executes_at_resting_price() -> None:
    book = LimitOrderBook()
    book.submit(limit("a1", Side.SELL, 5, "101.00", "maker"))
    trades = book.submit(limit("b1", Side.BUY, 5, "102.00", "taker"))
    assert [(t.price, t.quantity) for t in trades] == [(Decimal("101.00"), 5)]
    assert book.best_ask is None


def test_price_priority() -> None:
    book = LimitOrderBook()
    book.submit(limit("a2", Side.SELL, 2, "102.00"))
    book.submit(limit("a1", Side.SELL, 2, "101.00"))
    trades = book.submit(market("m", Side.BUY, 3))
    assert [t.maker_order_id for t in trades] == ["a1", "a2"]


def test_time_priority_within_level() -> None:
    book = LimitOrderBook()
    book.submit(limit("first", Side.SELL, 2, "101.00"))
    book.submit(limit("second", Side.SELL, 2, "101.00"))
    trades = book.submit(market("m", Side.BUY, 3))
    assert [t.maker_order_id for t in trades] == ["first", "second"]
    assert book.order("second").remaining == 1


def test_partial_fill_rests_remainder() -> None:
    book = LimitOrderBook()
    book.submit(limit("ask", Side.SELL, 3, "101.00"))
    book.submit(limit("bid", Side.BUY, 5, "101.00"))
    assert book.order("bid").remaining == 2
    assert book.best_bid == Decimal("101.00")


def test_unfilled_market_quantity_is_discarded() -> None:
    book = LimitOrderBook()
    order = market("m", Side.BUY, 10)
    assert book.submit(order) == []
    assert order.remaining == 10
    assert book.order("m") is None


def test_cancel() -> None:
    book = LimitOrderBook()
    book.submit(limit("b", Side.BUY, 5, "99.00"))
    assert book.cancel("b") is True
    assert book.cancel("b") is False
    assert book.best_bid is None


def test_spread_mid_and_depth() -> None:
    book = LimitOrderBook()
    book.submit(limit("b", Side.BUY, 7, "99.00"))
    book.submit(limit("a", Side.SELL, 9, "101.00"))
    assert book.spread == Decimal("2.00")
    assert book.mid_price == Decimal("100.00")
    assert book.depth(Side.SELL, 1) == [(Decimal("101.00"), 9)]


def test_rejects_invalid_tick_and_duplicate_id() -> None:
    book = LimitOrderBook("0.05")
    with pytest.raises(ValueError, match="aligned"):
        book.submit(limit("x", Side.BUY, 1, "99.03"))
    book.submit(limit("x", Side.BUY, 1, "99.05"))
    with pytest.raises(ValueError, match="duplicate"):
        book.submit(limit("x", Side.BUY, 1, "99.00"))


def test_order_validation() -> None:
    with pytest.raises(ValueError, match="positive"):
        limit("x", Side.BUY, 0, "10.00")
    with pytest.raises(ValueError, match="require"):
        Order("x", "p", Side.BUY, 1, OrderType.LIMIT)
