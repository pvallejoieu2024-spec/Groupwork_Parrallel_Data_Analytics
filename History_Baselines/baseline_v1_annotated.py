"""
VERSION 1 — Our first sequential baseline (historical reference).

PURPOSE: Read monthly BTS CSV files one by one and calculate the share of
non-cancelled flights delayed by >=15 minutes, grouped by origin airport
and scheduled hour. This is the first working reference to build upon.

WHY WE MOVED ON: It cannot measure congestion within a specific day;
'JFK at 08:00 across 36 months' is not the same as 'JFK at 08:00 today'.
It also has limited input validation, timing breakdown and memory metrics.

This is the original algorithm with explanatory comments, NOT a revised
production implementation. Keep historical versions separate from the
current runnable baseline to avoid confusion.
"""
import argparse
import calendar
import csv
import datetime
import glob
import os
import socket
import time

import pandas as pd

# Original default: specific to a teammate's Mac; use --data-dir on other machines.
DEFAULT_DATA_DIR = "~/Desktop/OSPC_Flight_Data/raw"
# Convert English month names in filenames into sortable numbers.
MONTH_NUMBER = {name: i for i, name in enumerate(calendar.month_name) if name}


def month_key(path):
    """Map 'BTS_Flights_January_2024.csv' to (2024, 1) for sorting."""
    _, _, month_name, year = os.path.basename(path)[:-4].split("_")
    return int(year), MONTH_NUMBER[month_name]


def list_month_files(data_dir, n_months):
    """Find files recursively and select first N in chronological order."""
    files = glob.glob(os.path.join(data_dir, "**", "BTS_Flights_*.csv"), recursive=True)
    files = sorted(files, key=month_key)
    if len(files) < n_months:
        raise SystemExit(f"Found {len(files)} monthly files in {data_dir}, "
                         f"but --months is {n_months}.")
    # --months is the workload-size control for scaling experiments.
    return files[:n_months]


def process_month(path):
    """Reduce one month's flights into integer counts per airport and hour."""
    # Read only four columns rather than loading the entire 36-column CSV.
    cols = ["ORIGIN", "CRS_DEP_TIME", "DEP_DEL15", "CANCELLED"]
    df = pd.read_csv(path, usecols=cols)
    # 1435 becomes 14: integer division gives scheduled hour.
    df["HOUR"] = df["CRS_DEP_TIME"] // 100
    # Cancelled flights do not contribute to this version's denominator.
    df = df[df["CANCELLED"] == 0]
    # ISSUE: No FL_DATE group => cannot distinguish a busy day from a quiet day.
    # 'count' ignores missing DEP_DEL15; 'sum' counts the 1s.
    return df.groupby(["ORIGIN", "HOUR"]).agg(
        n_flights=("DEP_DEL15", "count"),
        n_delayed=("DEP_DEL15", "sum"),
    )


def save_timing(path, row):
    """Append execution metadata for the eventual scaling analysis."""
    new_file = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row))
        if new_file:
            writer.writeheader()
        writer.writerow(row)
    # ISSUE: Unlike later versions, does not validate an existing CSV header.


def main():
    """Process months sequentially, summarize and save timings/results."""
    parser = argparse.ArgumentParser(description="Sequential baseline")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR,
                        help="folder containing the monthly BTS CSV files")
    parser.add_argument("--months", type=int, default=36,
                        help="number of months to process (size parameter)")
    parser.add_argument("--repetition", type=int, default=1,
                        help="repetition number (the brief asks for at least 5)")
    parser.add_argument("--results-dir", default="results",
                        help="where to save the timings and the result table")
    args = parser.parse_args()

    data_dir = os.path.expanduser(args.data_dir)
    files = list_month_files(data_dir, args.months)

    # Total wall-clock time for reading + processing + combining only.
    start = time.perf_counter()
    # One month at a time = sequential. A parallel version will distribute work.
    # Notice this list comprehension processes one file AFTER another; it does not use workers.
    partials = [process_month(f) for f in files]
    # Add integer counts first; take the ratio only after aggregation.
    result = pd.concat(partials).groupby(["ORIGIN", "HOUR"]).sum()
    # Divide the number of flagged late flights by the number with a known flag.
    # BTS DEP_DEL15 is 1 for 15 minutes OR MORE (not strictly >15 minutes).
    result["delay_share"] = result["n_delayed"] / result["n_flights"]
    elapsed = time.perf_counter() - start

    # 100 is an arbitrary filter against very small groups; justify it if used.
    busy = result[result["n_flights"] >= 100]
    print(busy.sort_values("delay_share", ascending=False).head(10))
    print(f"{args.months} months processed in {elapsed:.2f} seconds")

    os.makedirs(args.results_dir, exist_ok=True)
    result.to_csv(os.path.join(args.results_dir, f"baseline_{args.months}m.csv"))
    # Log how long this experiment took and where it ran. These entries
    # become the input for later speedup plots, not the raw flight rows.
    save_timing(os.path.join(args.results_dir, "timings.csv"), {
        "version": "baseline",
        "workers": 1,
        "months": args.months,
        "repetition": args.repetition,
        "elapsed_s": round(elapsed, 3),
        "node": socket.gethostname(),
        "job_id": os.environ.get("SLURM_JOB_ID", "local"),
        "date": datetime.datetime.now().isoformat(timespec="seconds"),
    })


if __name__ == "__main__":
    main()
