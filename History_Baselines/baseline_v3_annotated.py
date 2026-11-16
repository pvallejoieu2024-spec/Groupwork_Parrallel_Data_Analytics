"""
VERSION 3 — My proposed improved sequential baseline (development version).

WHY THIS VERSION WAS NEEDED:
Version 2 preserved a potentially large table of airport-date-hour groups
for every month. V3 reduces each month to smaller aggregate tables and
six correlation sums, which can be added across months (and later workers).
It also supports changing the first/last data year and analyzes airline,
weekday, delay minutes, taxi-out, and reported delay causes.

MAIN NEW DECISIONS: monthly summary tables; integer counts and minute
totals to support exact checks; compute percentages only after combining;
Pearson correlation from mergeable sufficient statistics; richer outputs.
This is STILL a sequential program, not the multiprocessing implementation.

NEXT PLANNED CHANGE: extend the experiment period from 2023–2025 to
2015–2025 (132 months). This historical copy STILL defaults to 2023–2025.
The 2015 expansion is a plan, not a completed or cluster-tested run.
To try it after the earlier monthly data is available, pass
--first-year 2015 --last-year 2025 --months 132.
The current code treats missing DEP_DELAY as zero for the mean, and
converts minute values to rounded integer totals. Validate those choices.
The statement that memory stays "almost flat" is a design intent, not an
independently verified benchmark.

Sequential baseline for Flight Delay Prediction & Airport Congestion.

Research question:
Which US airports and hours concentrate the most departure delays,
and how does the number of scheduled flights relate to delay share?

Usage:
    python history/baseline_v3_annotated.py --months 1
    python history/baseline_v3_annotated.py --months 132 --repetition 2
    python history/baseline_v3_annotated.py --first-year 2023 --months 36

The script processes files sequentially, one month at a time. Each month
is reduced to a few small tables of counts and minute totals, so memory
stays almost flat however many months are processed. All counts and
minutes are whole numbers, so the monthly tables add up exactly.

Outputs (in --results-dir, default results/):
    timings.csv                          one row per run (appended)
    congestion_airport_hour_<N>m.csv     per airport and hour
    congestion_by_level_<N>m.csv         per congestion level
    congestion_carrier_level_<N>m.csv    per airline and congestion level
    congestion_weekday_level_<N>m.csv    per day of week and congestion level
    congestion_summary_<N>m.csv          totals and correlation
"""

import argparse
import calendar
import csv
import datetime
import math
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
        PROJECT_ROOT / "data" / "OSPC_Flight_Data" / "raw"
    )
).expanduser()

FIRST_YEAR = 2023
LAST_YEAR = 2025

COLUMNS = [
    "FL_DATE",
    "DAY_OF_WEEK",
    "OP_UNIQUE_CARRIER",
    "ORIGIN",
    "CRS_DEP_TIME",
    "DEP_DELAY",
    "DEP_DEL15",
    "TAXI_OUT",
    "CANCELLED",
    "CARRIER_DELAY",
    "WEATHER_DELAY",
    "NAS_DELAY",
    "SECURITY_DELAY",
    "LATE_AIRCRAFT_DELAY",
]

# Compact column types: codes and dates repeat a lot, so "category"
# stores each distinct value once; numbers use 4 bytes instead of 8.
DTYPES = {
    "FL_DATE": "category",
    "DAY_OF_WEEK": "int8",
    "OP_UNIQUE_CARRIER": "category",
    "ORIGIN": "category",
    "CRS_DEP_TIME": "float32",
    "DEP_DELAY": "float32",
    "DEP_DEL15": "float32",
    "TAXI_OUT": "float32",
    "CANCELLED": "float32",
    "CARRIER_DELAY": "float32",
    "WEATHER_DELAY": "float32",
    "NAS_DELAY": "float32",
    "SECURITY_DELAY": "float32",
    "LATE_AIRCRAFT_DELAY": "float32",
}

# Delay-cause columns (filled only for flights delayed 15+ minutes)
# and the names of their minute totals in the result tables
CAUSES = {
    "CARRIER_DELAY": "carrier_delay_min",
    "WEATHER_DELAY": "weather_delay_min",
    "NAS_DELAY": "nas_delay_min",
    "SECURITY_DELAY": "security_delay_min",
    "LATE_AIRCRAFT_DELAY": "late_aircraft_delay_min",
}

MINUTE_COLUMNS = ["DEP_DELAY", "TAXI_OUT", *CAUSES]

GROUP_COLUMNS = ["FL_DATE", "ORIGIN", "HOUR"]

# Congestion levels: scheduled departures from one airport in one hour
# of one day
CONGESTION_BINS = [0, 2, 5, 10, 20, 40, 1000]
CONGESTION_LABELS = ["1-2", "3-5", "6-10", "11-20", "21-40", "41+"]

# Totals computed for every group of valid departures
FULL_AGG = {
    "valid_departures": ("DEP_DEL15", "size"),
    "delayed_flights": ("DEP_DEL15", "sum"),
    "dep_delay_min": ("DEP_DELAY", "sum"),
    "taxi_out_min": ("TAXI_OUT", "sum"),
    "taxi_out_flights": ("TAXI_OUT_KNOWN", "sum"),
    **{name: (col, "sum") for col, name in CAUSES.items()},
}

SHORT_AGG = {
    key: FULL_AGG[key]
    for key in ["valid_departures", "delayed_flights", "dep_delay_min"]
}


# ============================================================
# 2. FIND MONTHLY FILES
# ============================================================


# CHANGED FROM V2: configurable year range, allowing larger workloads.
# NOTE: current constants STILL default to 2023–2025 (36 months).
# For 132 months, pass --first-year 2015 --last-year 2025 --months 132.
# CHANGED FROM V2: this file finder accepts an arbitrary year range.
# For 2015–2025, set --first-year 2015 --last-year 2025 --months 132.
def list_month_files(data_dir, n_months, first_year, last_year):
    """Select the first n_months monthly CSV files, in date order."""

    all_files = [
        data_dir / str(year)
        / f"BTS_Flights_{calendar.month_name[month]}_{year}.csv"
        for year in range(first_year, last_year + 1)
        for month in range(1, 13)
    ]

    if not 1 <= n_months <= len(all_files):
        raise ValueError(
            f"--months must be between 1 and {len(all_files)} "
            f"for {first_year}-{last_year}"
        )

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


# EXPANDED: 14 input variables cover airlines, weekdays, taxi-out and delay causes.
# More columns increase work relative to v2; timing comparisons need care.
def read_month(path):
    """Read only the variables needed for congestion analysis."""

    # Read the same selected columns for every month so outputs are comparable.
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


# NEW: assign congestion to EACH FLIGHT using airport + date + hour counts.
# This lets us group the same flights by airline and by weekday.
# NEW IN V3: attach the actual number of scheduled flights to each row.
# That makes the same congestion classification usable for airline and
# weekday analyses, not just the airport-date-hour summary.
def prepare(df):
    """Add the scheduled hour and the congestion level of every flight."""

    # Remove rows without the information needed to form a group
    df = df.dropna(
        subset=["FL_DATE", "ORIGIN", "CRS_DEP_TIME"]
    ).copy()

    # Extract scheduled departure hour and keep valid hours
    df["HOUR"] = (df["CRS_DEP_TIME"] // 100).astype("int8")
    df = df[df["HOUR"].between(0, 23)]

    # Congestion: how many flights (including cancelled ones) were
    # scheduled from the same airport, in the same hour, on the same day
    df["FLIGHTS_IN_HOUR"] = (
        df.groupby(GROUP_COLUMNS, observed=True)["HOUR"]
        .transform("size")
    )

    df["LEVEL"] = pd.cut(
        df["FLIGHTS_IN_HOUR"],
        bins=CONGESTION_BINS,
        labels=CONGESTION_LABELS
    )

    return df



# NEW: filter cancellations/invalid flags and convert minute/count data to integers.
# IMPORTANT ASSUMPTION: missing minute values are treated as 0; validate this.
# NEW IN V3: convert minute totals to integer units before summing.
# The integer totals are order-independent; however, filling missing
# DEP_DELAY with zero changes the meaning of the mean delay measure.
def valid_departures(df):
    """Non-cancelled flights with a valid delay indicator, as integers."""

    valid = df[
        (df["CANCELLED"] == 0)
        & (df["DEP_DEL15"].isin([0, 1]))
    ].copy()

    valid["DEP_DEL15"] = valid["DEP_DEL15"].astype("int8")

    # Taxi-out time is sometimes missing: count the flights that have it
    valid["TAXI_OUT_KNOWN"] = valid["TAXI_OUT"].notna().astype("int8")

    # Minutes are whole numbers in BTS; empty cause columns mean 0
    # minutes. Integers make the monthly totals add up exactly.
    valid[MINUTE_COLUMNS] = (
        valid[MINUTE_COLUMNS].fillna(0).round().astype("int32")
    )

    return valid



# HELPER: reuse one aggregation pattern across dimensions.
def totals(frame, keys, agg):
    """Sum the given totals per group, as int64."""

    return (
        frame.groupby(keys, observed=True)
        .agg(**agg)
        .astype("int64")
    )



# MAJOR MEMORY REDESIGN: output only compact monthly aggregate tables,
# not every airport-date-hour record for the entire multi-year dataset.
# BIG CHANGE FROM V2: return several SMALL mergeable monthly tables and
# correlation statistics, rather than retain every daily congestion row
# until the final combination.
def process_month(df):
    """
    Reduce one month to small tables of counts and minute totals.

    Returns a dict of tables (DataFrames) plus the sums needed for the
    correlation, so that months can be combined by simple addition.
    """

    df = prepare(df)
    valid = valid_departures(df)

    # A. Per airport and hour
    airport_hour = (
        df.groupby(["ORIGIN", "HOUR"], observed=True)
        .size()
        .rename("scheduled_flights")
        .to_frame()
        .join(totals(valid, ["ORIGIN", "HOUR"], FULL_AGG), how="left")
        .fillna(0)
        .astype("int64")
    )

    # B. One row per airport-date-hour (used for levels and correlation)
    adh = (
        df.groupby(GROUP_COLUMNS, observed=True)
        .size()
        .rename("scheduled_flights")
        .to_frame()
        .join(
            valid.groupby(GROUP_COLUMNS, observed=True).agg(
                valid_departures=("DEP_DEL15", "size"),
                delayed_flights=("DEP_DEL15", "sum"),
            ),
            how="left"
        )
        .fillna(0)
    )

    adh_level = pd.cut(
        adh["scheduled_flights"],
        bins=CONGESTION_BINS,
        labels=CONGESTION_LABELS
    ).rename("LEVEL")

    # C. Per congestion level
    by_level = (
        adh.groupby(adh_level, observed=True)
        .size()
        .rename("airport_date_hours")
        .to_frame()
        .join(totals(valid, "LEVEL", FULL_AGG), how="left")
        .fillna(0)
        .astype("int64")
    )

    # D. Per airline and congestion level
    carrier_level = totals(
        valid, ["OP_UNIQUE_CARRIER", "LEVEL"], SHORT_AGG
    )

    # Airline categories can differ by monthly CSV; convert codes to text
    # before combining to avoid mismatched category levels.
    # Store airline codes as plain text, so the combined table is the
    # same whatever order the months are added in
    carrier_level.index = carrier_level.index.set_levels(
        carrier_level.index.levels[0].astype(str),
        level="OP_UNIQUE_CARRIER"
    )

    # E. Per day of week and congestion level
    weekday_level = totals(
        valid, ["DAY_OF_WEEK", "LEVEL"], SHORT_AGG
    )

    # Keeping these six values means we can calculate overall correlation
    # without keeping millions of daily airport-hour rows in memory.
    # F. Sums for the correlation between flights in an airport-date-hour
    #    (x) and the share of its departures delayed (y)
    with_departures = adh[adh["valid_departures"] > 0]
    x = with_departures["scheduled_flights"].astype("float64")
    y = (
        with_departures["delayed_flights"]
        / with_departures["valid_departures"]
    )

    corr_sums = pd.Series({
        "n": len(with_departures),
        "sx": x.sum(),
        "sy": y.sum(),
        "sxx": (x * x).sum(),
        "syy": (y * y).sum(),
        "sxy": (x * y).sum(),
    })

    return {
        "airport_hour": airport_hour,
        "by_level": by_level,
        "carrier_level": carrier_level,
        "weekday_level": weekday_level,
        "corr_sums": corr_sums,
    }


# ============================================================
# 5. COMBINE AND FINALIZE
# ============================================================

TABLES = ["airport_hour", "by_level", "carrier_level", "weekday_level"]



# NEW: combine MONTHLY COUNTS (not averages or percentages).
# Integer counts and minute totals should add exactly across worker order.
def combine(partials):
    """Add up the monthly tables (order does not matter)."""

    combined = {}

    for name in TABLES:
        stacked = pd.concat([p[name] for p in partials])
        combined[name] = (
            stacked.groupby(level=stacked.index.names, observed=True)
            .sum()
        )

    combined["corr_sums"] = sum(p["corr_sums"] for p in partials)

    return combined



# NEW: only AFTER monthly aggregation compute ratios and means.
# NOTE: mean departure delay treats missing DEP_DELAY as zero in current code.
def add_rates(table):
    """Turn totals into shares and averages (floats)."""

    table = table.copy()
    valid = table["valid_departures"].replace(0, float("nan"))

    table["delay_share"] = table["delayed_flights"] / valid
    table["mean_dep_delay_min"] = table["dep_delay_min"] / valid

    if "taxi_out_min" in table:
        table["mean_taxi_out_min"] = (
            table["taxi_out_min"]
            / table["taxi_out_flights"].replace(0, float("nan"))
        )

        cause_total = table[list(CAUSES.values())].sum(axis=1)
        cause_total = cause_total.replace(0, float("nan"))

        for name in CAUSES.values():
            share = name.replace("_delay_min", "_share")
            table[share] = table[name] / cause_total

    return table



# NEW: compute Pearson r from six additive summary statistics.
# Thus no need to retain all individual airport-date-hour rows.
def correlation(s):
    """Pearson correlation from the accumulated sums."""

    n = s["n"]
    num = n * s["sxy"] - s["sx"] * s["sy"]
    den = math.sqrt(
        (n * s["sxx"] - s["sx"] ** 2) * (n * s["syy"] - s["sy"] ** 2)
    )

    return num / den if den else float("nan")



# HELPER: compute final rates and global correlation.
def finalize(combined):
    """Final result tables and the correlation."""

    results = {name: add_rates(combined[name]) for name in TABLES}
    results["by_level"].index.name = "flights_in_hour"
    corr = correlation(combined["corr_sums"])

    return results, corr


# ============================================================
# 6. SEQUENTIAL BASELINE
# ============================================================


# The reading/compute/combine timing decomposition remains in place.
# This is still a SEQUENTIAL version, despite its parallel-friendly reductions.
def run_baseline(files):
    """Run the sequential analysis and record execution times."""

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

        partials.append(process_month(df))

        compute_time += time.perf_counter() - compute_start

        # Release raw monthly data
        del df

    # ========================================================
    # 7. COMBINE MONTHLY RESULTS
    # ========================================================

    combine_start = time.perf_counter()

    results, corr = finalize(combine(partials))

    combine_time = time.perf_counter() - combine_start

    total_time = time.perf_counter() - total_start

    times = {
        "read_s": round(read_time, 3),
        "compute_s": round(compute_time, 3),
        "combine_s": round(combine_time, 3),
        "total_s": round(total_time, 3),
    }

    return results, corr, times


# ============================================================
# 8. DISPLAY RESULTS
# ============================================================


# NEW: richer readable presentation of congestion results.
def display(results, corr, n_months, times):

    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    pd.set_option("display.precision", 3)

    airport_hour = results["airport_hour"]
    by_level = results["by_level"]

    busy = airport_hour[airport_hour["valid_departures"] >= 100]
    top_10 = busy.sort_values(
        ["delay_share", "delayed_flights"],
        ascending=[False, False]
    ).head(10)

    print("\nTop 10 airport-hours by delay share:")
    print(top_10[[
        "scheduled_flights", "valid_departures",
        "delay_share", "mean_dep_delay_min", "mean_taxi_out_min"
    ]])

    print("\nBy congestion level")
    print("(flights scheduled from one airport in one hour of one day):")
    print(by_level[[
        "airport_date_hours", "valid_departures", "delay_share",
        "mean_dep_delay_min", "mean_taxi_out_min",
        "nas_share", "late_aircraft_share", "weather_share",
        "carrier_share",
    ]])

    print("\nDelay share by day of week (1 = Monday) and congestion level:")
    print(
        results["weekday_level"]["delay_share"]
        .unstack("LEVEL")
    )

    print(
        "\nCorrelation between flights in an airport-date-hour "
        f"and its delay share: {corr:.3f}"
    )

    print("\n------------------------------------------")
    print(" DATA SUMMARY")
    print("------------------------------------------")
    print(f"Months processed:      {n_months}")
    print(f"Scheduled flights:     {airport_hour['scheduled_flights'].sum():,}")
    print(f"Valid departures:      {airport_hour['valid_departures'].sum():,}")
    print(f"Delayed departures:    {airport_hour['delayed_flights'].sum():,}")
    print(f"Airport-date-hours:    {by_level['airport_date_hours'].sum():,}")

    print("\n------------------------------------------")
    print(" EXECUTION TIMES")
    print("------------------------------------------")
    print(f"CSV reading:           {times['read_s']:.2f} seconds")
    print(f"Monthly computation:   {times['compute_s']:.2f} seconds")
    print(f"Final aggregation:     {times['combine_s']:.2f} seconds")
    print(f"TOTAL:                 {times['total_s']:.2f} seconds")


# ============================================================
# 9. SAVE RESULTS
# ============================================================


# Peak RSS measures a process high-water mark, not total CSV disk size.
def peak_memory_mib():
    """Peak memory (resident set size) of this process, in MiB."""

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    # Linux reports KiB, macOS reports bytes
    if sys.platform == "darwin":
        return round(peak / 2**20, 1)

    return round(peak / 2**10, 1)



# Keeps timing records schema-consistent; include node and Slurm job ID.
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



# EXPANDED: outputs airport-hour, congestion, carrier, weekday, summary tables.
def save_results(results_dir, n_months, repetition, results, corr, times):
    """Save the result tables and one timing row for this run."""

    results_dir.mkdir(parents=True, exist_ok=True)

    for name, table in results.items():
        table.to_csv(results_dir / f"congestion_{name}_{n_months}m.csv")

    airport_hour = results["airport_hour"]

    pd.Series({
        "months": n_months,
        "scheduled_flights": airport_hour["scheduled_flights"].sum(),
        "valid_departures": airport_hour["valid_departures"].sum(),
        "delayed_flights": airport_hour["delayed_flights"].sum(),
        "correlation_flights_vs_delay_share": round(corr, 6),
    }, dtype=object).to_csv(
        results_dir / f"congestion_summary_{n_months}m.csv",
        header=["value"]
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
        "--first-year",
        type=int,
        default=FIRST_YEAR,
        help=f"First year of data (default {FIRST_YEAR})"
    )

    parser.add_argument(
        "--last-year",
        type=int,
        default=LAST_YEAR,
        help=f"Last year of data (default {LAST_YEAR})"
    )

    parser.add_argument(
        "--months",
        type=int,
        default=12 * (LAST_YEAR - FIRST_YEAR + 1),
        help="Number of monthly files to process (size parameter)"
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

    files = list_month_files(
        args.data_dir.expanduser(),
        args.months,
        args.first_year,
        args.last_year
    )

    print("\n==========================================")
    print(" SEQUENTIAL AIRPORT CONGESTION BASELINE")
    print("==========================================")
    print(f"Data directory: {args.data_dir}")
    print(f"Months requested: {args.months} "
          f"(from {args.first_year}-01)")

    results, corr, times = run_baseline(files)

    display(results, corr, args.months, times)

    save_results(
        args.results_dir,
        args.months,
        args.repetition,
        results,
        corr,
        times
    )


if __name__ == "__main__":
    main()
