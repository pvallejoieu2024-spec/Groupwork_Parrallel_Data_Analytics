"""
Check that the process-pool version gives the same results as the baseline.

Counts and minute totals (integers) must match EXACTLY.
Shares, means and the correlation (floats) must match within a small
relative tolerance, because adding the months in a different order can
change the last digits of a floating-point result.

Usage (small and fast):
    python tests/check_equivalence.py --months 3 --workers 2
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "jobs"))
import baseline_congestion2 as base  # noqa: E402
import parallel_pool  # noqa: E402

RTOL = 1e-9   # floats: relative tolerance


def compare(name, a, b):
    a = a.sort_index()
    b = b.sort_index()
    assert list(a.columns) == list(b.columns), f"{name}: different columns"
    rows_a = [str(k) for k in a.index.to_flat_index()]
    rows_b = [str(k) for k in b.index.to_flat_index()]
    assert rows_a == rows_b, f"{name}: different rows"

    for col in a.columns:
        x, y = a[col].to_numpy(), b[col].to_numpy()
        if np.issubdtype(x.dtype, np.integer):
            assert np.array_equal(x, y), f"{name}.{col}: integers differ"
        else:
            assert np.allclose(x, y, rtol=RTOL, atol=0, equal_nan=True), \
                f"{name}.{col}: floats differ beyond tolerance"
    print(f"  OK  {name}  ({len(a)} rows)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=base.DEFAULT_DATA_DIR)
    parser.add_argument("--months", type=int, default=3)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--first-year", type=int, default=base.FIRST_YEAR)
    parser.add_argument("--last-year", type=int, default=base.LAST_YEAR)
    args = parser.parse_args()

    files = base.list_month_files(
        args.data_dir.expanduser(), args.months, args.first_year, args.last_year
    )

    print(f"Baseline vs pool ({args.workers} workers), {args.months} months:")
    seq, seq_corr, _ = base.run_baseline(files)
    par, par_corr, _ = parallel_pool.run_pool(files, args.workers)

    for name in base.TABLES:
        compare(name, seq[name], par[name])

    assert np.isclose(seq_corr, par_corr, rtol=RTOL, atol=0), "correlation differs"
    print(f"  OK  correlation ({seq_corr:.6f})")
    print("PASSED: the pool version matches the baseline.")


if __name__ == "__main__":
    main()
