"""
Sequential baseline for Flight Delay Prediction & Airport Congestion.

Research question:
Which US airports and hours concentrate the most departure delays,
and how does the number of scheduled flights relate to delay share?

Usage:
    python jobs/baseline_congestion.py --months 1
    python jobs/baseline_congestion.py --months 36 --repetition 2

Custom data directory:
    python jobs/baseline_congestion.py \
        --data-dir /path/to/raw \
        --months 36

The script processes files sequentially, one month at a time. Only the
small per-month summaries are kept, so memory grows slowly with the
number of months (about 140 MiB for 1 month, 450 MiB for 36).

Outputs (in --results-dir, default results/):
    timings.csv                          one row per run (appended)
    congestion_airport_hour_<N>m.csv     delay share per airport and hour
    congestion_by_level_<N>m.csv         delay share per congestion level
"""

import argparse
import calendar
import csv
import datetime
import os
import resource
import socket
import sys
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

# Compact column types: airport codes and dates repeat a lot, so
# "category" stores each distinct value once. This keeps the memory of
# one month small (about 90 MiB instead of about 560 MiB).
DTYPES = {
    "FL_DATE": "category",
    "ORIGIN": "category",
    "CRS_DEP_TIME": "float32",
    "DEP_DEL15": "float32",
    "CANCELLED": "float32",
}

GROUP_COLUMNS = ["FL_DATE", "ORIGIN", "HOUR"]

# Congestion levels: scheduled departures from one airport in one hour
# of one day. The labels are used in the congestion-level table.
CONGESTION_BINS = [0, 2, 5, 10, 20, 40, 1000]
CONGESTION_LABELS = ["1-2", "3-5", "6-10", "11-20", "21-40", "41+"]


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

    # Note: do not use low_memory=False here. It makes pandas parse the
    # whole file in one block and multiplies the peak memory by about 5.
    return pd.read_csv(
        path,
        usecols=COLUMNS,
        dtype=DTYPES
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
    df["HOUR"] = (df["CRS_DEP_TIME"] // 100).astype("int8")

    # Keep valid scheduled hours
    df = df[df["HOUR"].between(0, 23)]

    # A. Count all scheduled flights, including cancellations
    scheduled = (
        df.groupby(GROUP_COLUMNS, observed=True)
        .size()
        .rename("scheduled_flights")
    )

    # B. Keep non-cancelled flights with a valid delay indicator
    valid = df[
        (df["CANCELLED"] == 0)
        & (df["DEP_DEL15"].isin([0, 1]))
    ]

    # C. Count valid and delayed departures
    departures = valid.groupby(GROUP_COLUMNS, observed=True).agg(
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

    # Store the date as a real date (8 bytes) instead of text, so the
    # 36 monthly tables stay small when they are combined at the end
    result.index = result.index.set_levels(
        pd.to_datetime(result.index.levels[0]), level="FL_DATE"
    )

    return result


# ============================================================
# 5. ANSWER THE QUESTION WITH THE AIRPORT-DATE-HOUR TABLE
# ============================================================

def summarize(result):
    """
    Use the airport-date-hour table to relate congestion to delays.

    Returns:
        summary    delay share per airport and hour (whole period)
        by_level   delay share per congestion level
        corr       correlation between flights in an hour and delay share
    """

    # A. Airport-hour summary over the whole period (as before)
    summary = result.groupby(level=["ORIGIN", "HOUR"], observed=True)[
        ["scheduled_flights", "valid_departures", "delayed_flights"]
    ].sum()

    summary["delay_share"] = (
        summary["delayed_flights"]
        / summary["valid_departures"].replace(0, float("nan"))
    )

    # B. Congestion levels: group every airport-date-hour by how many
    #    flights were scheduled in it, then compute the delay share of
    #    each level from the summed counts.
    level = pd.cut(
        result["scheduled_flights"],
        bins=CONGESTION_BINS,
        labels=CONGESTION_LABELS
    )

    by_level = result.groupby(level, observed=True)[
        ["valid_departures", "delayed_flights"]
    ].sum()

    by_level["airport_date_hours"] = (
        result.groupby(level, observed=True).size()
    )

    by_level["delay_share"] = (
        by_level["delayed_flights"]
        / by_level["valid_departures"].replace(0, float("nan"))
    )

    by_level.index.name = "flights_in_hour"

    # C. Correlation between the number of flights scheduled in an
    #    airport-date-hour and the share of its departures delayed
    with_departures = result[result["valid_departures"] > 0]

    corr = with_departures["scheduled_flights"].corr(
        with_departures["delayed_flights"]
        / with_departures["valid_departures"]
    )

    return summary, by_level, corr


# ============================================================
# 6. SEQUENTIAL BASELINE
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
    # 7. COMBINE MONTHLY RESULTS
    # ========================================================

    combine_start = time.perf_counter()

    # Each date is in exactly one monthly file, so the monthly tables
    # never share a row: stacking them gives the final airport-date-hour
    # table. (A groupby().sum() here would give the same counts but more
    # than doubles the peak memory on 3 million rows.)
    result = pd.concat(partials)
    del partials

    summary, by_level, corr = summarize(result)

    combine_time = time.perf_counter() - combine_start

    total_time = time.perf_counter() - total_start

    # ========================================================
    # 8. DISPLAY RESULTS
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

    print("\nDelay share by congestion level")
    print("(flights scheduled from one airport in one hour of one day):")
    print(by_level)

    print(
        "\nCorrelation between flights in an airport-date-hour "
        f"and its delay share: {corr:.3f}"
    )

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

    times = {
        "read_s": round(read_time, 3),
        "compute_s": round(compute_time, 3),
        "combine_s": round(combine_time, 3),
        "total_s": round(total_time, 3),
    }

    return summary, by_level, times


# ============================================================
# 9. SAVE RESULTS
# ============================================================

def peak_memory_mib():
    """Peak memory (resident set size) of this process, in MiB."""

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    # Linux reports KiB, macOS reports bytes
    if sys.platform == "darwin":
        return round(peak / 2**20, 1)

    return round(peak / 2**10, 1)


def save_timing(path, row):
    """Append one row to the timings CSV (write the header if new)."""

    new_file = not path.exists()

    # Refuse to append to a file with different columns (for example an
    # old timings file), which would silently mix up the values
    if not new_file:
        with open(path, newline="") as f:
            header = next(csv.reader(f), [])
        if header != list(row):
            raise ValueError(
                f"{path} has different columns: {header}. "
                "Rename or remove it before running again."
            )

    with open(path, "a", newline="") as f:

        writer = csv.DictWriter(f, fieldnames=list(row))

        if new_file:
            writer.writeheader()

        writer.writerow(row)


def save_results(results_dir, n_months, repetition,
                 summary, by_level, times):
    """Save the result tables and one timing row for this run."""

    results_dir.mkdir(parents=True, exist_ok=True)

    summary.to_csv(
        results_dir / f"congestion_airport_hour_{n_months}m.csv"
    )

    by_level.to_csv(
        results_dir / f"congestion_by_level_{n_months}m.csv"
    )

    save_timing(results_dir / "timings.csv", {
        "version": "baseline",
        "workers": 1,
        "months": n_months,
        "repetition": repetition,
        **times,
        "peak_mem_mib": peak_memory_mib(),
        "node": socket.gethostname(),
        "job_id": os.environ.get("SLURM_JOB_ID", "local"),
        "date": datetime.datetime.now().isoformat(timespec="seconds"),
    })

    print(f"\nResults saved in {results_dir}/")


# ============================================================
# 10. MAIN
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

    parser.add_argument(
        "--repetition",
        type=int,
        default=1,
        help="Repetition number (the brief asks for at least 5)"
    )

    parser.add_argument(
        "--results-dir",
        type=Path,
        default=PROJECT_ROOT / "results",
        help="Where to save the timings and the result tables"
    )

    args = parser.parse_args()

    summary, by_level, times = run_baseline(
        args.data_dir.expanduser(),
        args.months
    )

    save_results(
        args.results_dir,
        args.months,
        args.repetition,
        summary,
        by_level,
        times
    )


if __name__ == "__main__":
    main()
