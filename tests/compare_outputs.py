"""
Compare the result tables saved by a baseline run and a process-pool run.

jobs/baseline_congestion2.py saves  congestion_<table>_<N>m.csv
jobs/parallel_pool.py         saves  pool_<table>_<N>m.csv

When both versions run in the same job (jobs/compare_single_worker_job.sh),
both sets of tables are in the same folder. This script checks that they
are equivalent on the FULL dataset, with the same rules as
tests/check_equivalence.py:
    - counts and minute totals (integers): exactly equal
    - shares, means (floats): equal within a relative tolerance of 1e-9
    - correlation (saved rounded to 6 decimals): equal within 1e-6

Usage:
    python tests/compare_outputs.py results/single_worker/<JOB_ID> --months 132
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_equivalence import compare  # noqa: E402

# Number of index columns of each saved table
INDEX_COLUMNS = {
    "airport_hour": 2,    # ORIGIN, HOUR
    "by_level": 1,        # flights_in_hour
    "carrier_level": 2,   # OP_UNIQUE_CARRIER, LEVEL
    "weekday_level": 2,   # DAY_OF_WEEK, LEVEL
}


def read(path, n_index):
    return pd.read_csv(path, index_col=list(range(n_index)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("--months", type=int, default=132)
    args = parser.parse_args()

    folder, n = args.folder, args.months
    print(f"Comparing baseline and pool tables in {folder} ({n} months):")

    for name, n_index in INDEX_COLUMNS.items():
        base = read(folder / f"congestion_{name}_{n}m.csv", n_index)
        pool = read(folder / f"pool_{name}_{n}m.csv", n_index)
        compare(name, base, pool)

    base = pd.read_csv(folder / f"congestion_summary_{n}m.csv", index_col=0)["value"]
    pool = pd.read_csv(folder / f"pool_summary_{n}m.csv", index_col=0)["value"]
    for key in ["months", "scheduled_flights", "valid_departures", "delayed_flights"]:
        assert int(base[key]) == int(pool[key]), f"summary.{key} differs"
    corr_key = "correlation_flights_vs_delay_share"
    assert abs(float(base[corr_key]) - float(pool[corr_key])) <= 1e-6, "correlation differs"
    print(f"  OK  summary  (flights={int(base['scheduled_flights']):,}, "
          f"correlation={float(base[corr_key]):.6f})")

    print("PASSED: the pool output matches the baseline output.")


if __name__ == "__main__":
    main()
