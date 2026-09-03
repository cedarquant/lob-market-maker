from __future__ import annotations

import argparse
from pathlib import Path

from .simulation import MarketSimulation, save_result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the LOB market-making simulation")
    parser.add_argument("--steps", type=int, default=1_000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--output", type=Path, default=Path("results"))
    args = parser.parse_args()
    result = MarketSimulation(steps=args.steps, seed=args.seed).run()
    save_result(result, args.output)
    print(f"trades={result.total_trades} maker_fills={result.maker_fills}")
    print(f"inventory={result.final_inventory} pnl={result.final_pnl:.2f}")
    print(f"wrote {args.output / 'metrics.csv'} and {args.output / 'performance.svg'}")


if __name__ == "__main__":
    main()
