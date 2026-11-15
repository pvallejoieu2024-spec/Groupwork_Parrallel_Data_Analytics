"""
Sequential baseline: share of departures delayed >15 min, by airport and hour.

Usage (from the repo root):
    python jobs/baseline.py                                  # default folder, 36 months
    python jobs/baseline.py --months 3                       # quick test
    python jobs/baseline.py --data-dir /path/to/raw --months 12
"""
import argparse
import calendar
import glob
import os
import time

import pandas as pd

DEFAULT_DATA_DIR = "~/Desktop/OSPC_Flight_Data/raw"
MONTH_NUMBER = {name: i for i, name in enumerate(calendar.month_name) if name}


def month_key(path):
    """BTS_Flights_January_2024.csv -> (2024, 1), so files sort by date."""
    _, _, month_name, year = os.path.basename(path)[:-4].split("_")
    return int(year), MONTH_NUMBER[month_name]


def list_month_files(data_dir, n_months):
    """All monthly CSVs under data_dir, in date order, keeping the first n_months."""
    files = glob.glob(os.path.join(data_dir, "**", "BTS_Flights_*.csv"), recursive=True)
    files = sorted(files, key=month_key)
    if len(files) < n_months:
        raise SystemExit(f"Found {len(files)} monthly files in {data_dir}, "
                         f"but --months is {n_months}.")
    return files[:n_months]


def process_month(path):
    """Read one month and count flights and delayed departures by airport and hour."""
    cols = ["ORIGIN", "CRS_DEP_TIME", "DEP_DEL15", "CANCELLED"]
    df = pd.read_csv(path, usecols=cols)
    df["HOUR"] = df["CRS_DEP_TIME"] // 100
    df = df[df["CANCELLED"] == 0]
    return df.groupby(["ORIGIN", "HOUR"]).agg(
        n_flights=("DEP_DEL15", "count"),
        n_delayed=("DEP_DEL15", "sum"),
    )


def main():
    parser = argparse.ArgumentParser(description="Sequential baseline")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR,
                        help="folder containing the monthly BTS CSV files")
    parser.add_argument("--months", type=int, default=36,
                        help="number of months to process (size parameter)")
    args = parser.parse_args()

    data_dir = os.path.expanduser(args.data_dir)
    files = list_month_files(data_dir, args.months)

    start = time.perf_counter()
    partials = [process_month(f) for f in files]
    result = pd.concat(partials).groupby(["ORIGIN", "HOUR"]).sum()
    result["delay_share"] = result["n_delayed"] / result["n_flights"]
    elapsed = time.perf_counter() - start

    busy = result[result["n_flights"] >= 100]
    print(busy.sort_values("delay_share", ascending=False).head(10))
    print(f"{args.months} months processed in {elapsed:.2f} seconds")


if __name__ == "__main__":
    main()