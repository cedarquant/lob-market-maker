from decimal import Decimal

from lobmm import InventoryAwareMarketMaker, Side, Trade


def trade(aggressor: Side, quantity: int = 4) -> Trade:
    return Trade(1, 1, Decimal(100), quantity, aggressor, "maker", "taker", "market-maker", "other")


def test_long_inventory_skews_quotes_down() -> None:
    flat = InventoryAwareMarketMaker(inventory=0)
    long = InventoryAwareMarketMaker(inventory=50)
    flat_bid, flat_ask = flat.quotes(Decimal(100), Decimal("0.01"), 0)
    long_bid, long_ask = long.quotes(Decimal(100), Decimal("0.01"), 0)
    assert long_bid < flat_bid
    assert long_ask < flat_ask


def test_maker_sell_updates_inventory_and_cash() -> None:
    maker = InventoryAwareMarketMaker()
    maker.process_trade(trade(Side.BUY))
    assert maker.inventory == -4
    assert maker.cash == Decimal(400)
    assert maker.mark_to_market(Decimal(100)) == 0


def test_inventory_limit_caps_order_size() -> None:
    maker = InventoryAwareMarketMaker(order_size=10, max_inventory=100, inventory=96)
    assert maker.allowed_size(Side.BUY) == 4
    assert maker.allowed_size(Side.SELL) == 10


def test_quotes_align_to_tick() -> None:
    maker = InventoryAwareMarketMaker()
    bid, ask = maker.quotes(Decimal(100), Decimal("0.05"), 0.5)
    assert bid % Decimal("0.05") == 0
    assert ask % Decimal("0.05") == 0
    assert bid < ask
