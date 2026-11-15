"""
Sequential baseline for Flight Delay Prediction & Airport Congestion.

Research question:
Which US airports and hours concentrate the most departure delays,
and how does the number of scheduled flights relate to delay share?

Usage:
    python jobs/baseline_congestion.py --months 1
    python jobs/baseline_congestion.py --months 12
    python jobs/baseline_congestion.py --months 36

Custom data directory:
    python jobs/baseline_congestion.py \
        --data-dir /path/to/raw \
        --months 36

The script processes files sequentially, one month at a time.
"""

import argparse
import calendar
import os
import time
from pathlib import Path

import pandas as pd


# ============================================================
# 1. CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DATA_DIR = Path(
    os.environ.get(
        "FLIGHT_DATA_DIR",
        PROJECT_ROOT / "data" / "raw"
    )
).expanduser()

COLUMNS = [
    "FL_DATE",
    "ORIGIN",
    "CRS_DEP_TIME",
    "DEP_DEL15",
    "CANCELLED",
]

GROUP_COLUMNS = ["FL_DATE", "ORIGIN", "HOUR"]


# ============================================================
# 2. FIND MONTHLY FILES
# ============================================================

def list_month_files(data_dir, n_months):
    """Select monthly CSV files in chronological order."""

    if not 1 <= n_months <= 36:
        raise ValueError("--months must be between 1 and 36")

    all_files = [
        data_dir / str(year)
        / f"BTS_Flights_{calendar.month_name[month]}_{year}.csv"
        for year in range(2023, 2026)
        for month in range(1, 13)
    ]

    files = all_files[:n_months]

    missing = [path for path in files if not path.is_file()]

    if missing:
        raise FileNotFoundError(
            "The following datasets are missing:\n"
            + "\n".join(str(path) for path in missing)
        )

    return files


# ============================================================
# 3. READ MONTHLY DATA
# ============================================================

def read_month(path):
    """Read only the variables needed for congestion analysis."""

    return pd.read_csv(
        path,
        usecols=COLUMNS,
        low_memory=False
    )


# ============================================================
# 4. PROCESS ONE MONTH
# ============================================================

def process_month(df):
    """
    Calculate congestion and departure-delay statistics
    for each airport, date and scheduled departure hour.
    """

    # Remove rows without the information needed to form a group
    df = df.dropna(
        subset=["FL_DATE", "ORIGIN", "CRS_DEP_TIME"]
    ).copy()

    # Extract scheduled departure hour
    df["HOUR"] = df["CRS_DEP_TIME"] // 100

    # Keep valid scheduled hours
    df = df[df["HOUR"].between(0, 23)]

    # A. Count all scheduled flights, including cancellations
    scheduled = (
        df.groupby(GROUP_COLUMNS)
        .size()
        .rename("scheduled_flights")
    )

    # B. Keep non-cancelled flights with a valid delay indicator
    valid = df[
        (df["CANCELLED"] == 0)
        & (df["DEP_DEL15"].isin([0, 1]))
    ]

    # C. Count valid and delayed departures
    departures = valid.groupby(GROUP_COLUMNS).agg(
        valid_departures=("DEP_DEL15", "count"),
        delayed_flights=("DEP_DEL15", "sum"),
    )

    # D. Combine counts
    result = scheduled.to_frame().join(
        departures,
        how="left"
    )

    result[["valid_departures", "delayed_flights"]] = (
        result[["valid_departures", "delayed_flights"]]
        .fillna(0)
        .astype("int64")
    )

    return result


# ============================================================
# 5. SEQUENTIAL BASELINE
# ============================================================

def run_baseline(data_dir, n_months):
    """Run the sequential analysis and record execution times."""

    files = list_month_files(data_dir, n_months)

    print("\n==========================================")
    print(" SEQUENTIAL AIRPORT CONGESTION BASELINE")
    print("==========================================")
    print(f"Data directory: {data_dir}")
    print(f"Months requested: {n_months}")

    partials = []

    read_time = 0.0
    compute_time = 0.0

    total_start = time.perf_counter()

    # Sequential execution: one month after another
    for path in files:

        read_start = time.perf_counter()

        df = read_month(path)

        read_time += time.perf_counter() - read_start

        compute_start = time.perf_counter()

        partial = process_month(df)

        compute_time += time.perf_counter() - compute_start

        partials.append(partial)

        # Release raw monthly data
        del df

    # ========================================================
    # 6. COMBINE MONTHLY RESULTS
    # ========================================================

    combine_start = time.perf_counter()

    result = pd.concat(partials)

    result = result.groupby(level=GROUP_COLUMNS).sum()

    result["delay_share"] = (
        result["delayed_flights"]
        / result["valid_departures"].replace(0, float("nan"))
    )

    # Summarize airport-hour behavior across the full period
    summary = result.groupby(level=["ORIGIN", "HOUR"])[
        ["scheduled_flights", "valid_departures", "delayed_flights"]
    ].sum()

    summary["delay_share"] = (
        summary["delayed_flights"]
        / summary["valid_departures"].replace(0, float("nan"))
    )

    combine_time = time.perf_counter() - combine_start

    total_time = time.perf_counter() - total_start

    # ========================================================
    # 7. DISPLAY RESULTS
    # ========================================================

    busy = summary[
        summary["valid_departures"] >= 100
    ]

    top_10 = busy.sort_values(
        ["delay_share", "delayed_flights"],
        ascending=[False, False]
    ).head(10)

    print("\nTop 10 airport-hours by delay share:")
    print(top_10)

    print("\n------------------------------------------")
    print(" DATA SUMMARY")
    print("------------------------------------------")
    print(f"Months processed:      {n_months}")
    print(f"Scheduled flights:     {result['scheduled_flights'].sum():,}")
    print(f"Valid departures:      {result['valid_departures'].sum():,}")
    print(f"Delayed departures:    {result['delayed_flights'].sum():,}")
    print(f"Airport-date-hours:    {len(result):,}")

    print("\n------------------------------------------")
    print(" EXECUTION TIMES")
    print("------------------------------------------")
    print(f"CSV reading:           {read_time:.2f} seconds")
    print(f"Monthly computation:   {compute_time:.2f} seconds")
    print(f"Final aggregation:     {combine_time:.2f} seconds")
    print(f"TOTAL:                 {total_time:.2f} seconds")

    return result, summary


# ============================================================
# 8. MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="Sequential BTS airport congestion analysis"
    )

    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory containing the yearly BTS CSV folders"
    )

    parser.add_argument(
        "--months",
        type=int,
        default=36,
        help="Number of monthly files to process (1–36)"
    )

    args = parser.parse_args()

    run_baseline(
        args.data_dir.expanduser(),
        args.months
    )


if __name__ == "__main__":
    main()