"""[Analysis title]: [one-line question this script answers].

Usage:
    python analysis.py <input.csv> [--out-dir tmp/analysis]

Reproducible: re-running on the same input must produce the same outputs.
"""

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless-safe; must precede pyplot import
import matplotlib.pyplot as plt
import pandas as pd


def load(path: Path) -> pd.DataFrame:
    """Load and normalize the export (Frappe CSV conventions)."""
    df = pd.read_csv(path, dtype=str)  # pin dtypes; cast columns explicitly below
    df = df.replace("", pd.NA)
    # TODO: parse_dates / cast Check (0/1) fields to bool / cast numerics
    return df


def validate(df: pd.DataFrame) -> None:
    """Fail loudly on data that would silently corrupt the analysis."""
    if df.empty:
        sys.exit("Input has no rows.")
    # TODO: duplicate-key check, null counts, date-range sanity
    print(f"Rows: {len(df)}")
    print(df.isna().sum().to_string())


def analyze(df: pd.DataFrame) -> pd.DataFrame:
    """Vectorized Pandas only; state assumptions in comments here."""
    # TODO: groupby / pivot_table / resample
    return df


def plot(result: pd.DataFrame, out_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    # TODO: one chart, one question; title states the finding
    ax.set_title("TODO: finding, not chart type")
    ax.set_xlabel("TODO (units)")
    ax.set_ylabel("TODO (units)")
    fig.autofmt_xdate()
    out = out_dir / "chart.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Wrote {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("tmp/analysis"))
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    df = load(args.input)
    validate(df)
    result = analyze(df)
    plot(result, args.out_dir)
    result.to_csv(args.out_dir / "result.csv", index=False)


if __name__ == "__main__":
    main()
