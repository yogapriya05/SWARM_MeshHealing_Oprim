"""Generate the operational viability figure and its JSON source data."""
import argparse
import json
from pathlib import Path

from backend.app.breakeven import BreakevenConfig, analyze, plot


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the breakeven viability figure")
    parser.add_argument("--output", type=Path, default=Path("docs/figures/breakeven_feasibility.png"))
    parser.add_argument("--data", type=Path, default=Path("docs/figures/breakeven_feasibility.json"))
    parser.add_argument("--samples", type=int, default=100)
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("--samples must be positive")
    result = analyze(BreakevenConfig(samples_per_count=args.samples))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.data.parent.mkdir(parents=True, exist_ok=True)
    plot(result, str(args.output))
    args.data.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")
    print(f"wrote {args.data}")


if __name__ == "__main__":
    main()
