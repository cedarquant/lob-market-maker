from lobmm.simulation import MarketSimulation


def test_simulation_is_deterministic_and_bounded() -> None:
    first = MarketSimulation(steps=100, seed=11).run()
    second = MarketSimulation(steps=100, seed=11).run()
    assert first.final_pnl == second.final_pnl
    assert first.final_inventory == second.final_inventory
    assert first.max_abs_inventory <= 100
    assert len(first.snapshots) == 100
