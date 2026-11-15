"""
Shared code for every version (sequential and parallel).

The versions differ ONLY in how they call these functions:
    files = list_month_files(data_dir, n_months)
    partials = [compute_partial(read_month(f)) for f in files]   # <- parallelise this
    totals = combine(partials)
    result = finalize(totals)

Each month gives partial COUNTS (integers), so partials add up exactly.
"""
import calendar
import re
from pathlib import Path

import pandas as pd

# Only the columns we need -> less parsing, less memory.
USECOLS = ["FL_DATE", "ORIGIN", "CRS_DEP_TIME", "DEP_DELAY", "DEP_DEL15", "CANCELLED"]
DTYPES = {"ORIGIN": "string", "CRS_DEP_TIME": "int32",
          "DEP_DELAY": "float64", "DEP_DEL15": "float64", "CANCELLED": "float64"}

KEYS = ["ORIGIN", "HOUR"]
COUNT_COLS = ["n_scheduled", "n_cancelled", "n_operated", "n_delayed15", "sum_dep_delay"]

_MONTHS = {name: i for i, name in enumerate(calendar.month_name) if name}
_NAME = re.compile(r"BTS_Flights_([A-Za-z]+)_(\d{4})\.csv$")


def list_month_files(data_dir, n_months=None):
    """All monthly CSVs under data_dir, in date order; keep the first n_months (size parameter)."""
    found = []
    for p in Path(data_dir).rglob("BTS_Flights_*.csv"):
        m = _NAME.search(p.name)
        if m and m.group(1) in _MONTHS:
            found.append(((int(m.group(2)), _MONTHS[m.group(1)]), p))
    found.sort()
    files = [p for _, p in found]
    if not files:
        raise FileNotFoundError(f"no BTS_Flights_<Month>_<Year>.csv files in {data_dir}")
    if n_months is not None:
        if n_months > len(files):
            raise ValueError(f"asked for {n_months} months, only {len(files)} available")
        files = files[:n_months]
    return files


def read_month(path):
    """I/O + parsing: load one monthly CSV (only the needed columns)."""
    return pd.read_csv(path, usecols=USECOLS, dtype=DTYPES)


def compute_partial(df):
    """Computation: per (airport, scheduled hour) integer counts for one month.

    Returns (counts DataFrame, number of distinct days in this month).
    """
    df = df.assign(HOUR=(df["CRS_DEP_TIME"] // 100) % 24)   # 2400 -> hour 0
    cancelled = df["CANCELLED"].fillna(0).eq(1)
    operated = ~cancelled & df["DEP_DEL15"].notna()
    df = df.assign(
        n_scheduled=1,
        n_cancelled=cancelled.astype("int64"),
        n_operated=operated.astype("int64"),
        n_delayed15=(operated & df["DEP_DEL15"].eq(1)).astype("int64"),
        # delay minutes are whole numbers in BTS -> store as int so sums are exact
        sum_dep_delay=df["DEP_DELAY"].where(operated, 0).fillna(0).round().astype("int64"),
    )
    counts = df.groupby(KEYS, observed=True)[COUNT_COLS].sum()
    return counts, df["FL_DATE"].nunique()


def combine(partials):
    """Add up the partial results of several months (order does not matter)."""
    tables, days = zip(*partials)
    totals = pd.concat(tables).groupby(level=KEYS).sum().sort_index()
    return totals, int(sum(days))


def finalize(combined):
    """Turn exact counts into the indicators we report (floats)."""
    totals, n_days = combined
    out = totals.reset_index()
    out["flights_per_day"] = out["n_scheduled"] / n_days     # congestion: flights in that hour per day
    out["delay_share"] = out["n_delayed15"] / out["n_operated"].where(out["n_operated"] > 0)
    out["mean_dep_delay"] = out["sum_dep_delay"] / out["n_operated"].where(out["n_operated"] > 0)
    return out


def summary(result, top=10, min_flights_per_day=5):
    """Short text answer to the analytical question."""
    busy = result[result["flights_per_day"] >= min_flights_per_day]
    worst = busy.sort_values("delay_share", ascending=False).head(top)
    corr = busy["flights_per_day"].corr(busy["delay_share"])
    lines = [f"Airport-hours analysed: {len(result)} "
             f"({len(busy)} with >= {min_flights_per_day} flights/day)",
             f"Correlation flights/hour vs share delayed >15 min: {corr:.3f}",
             f"Top {top} most delayed airport-hours:"]
    for _, r in worst.iterrows():
        lines.append(f"  {r['ORIGIN']} {int(r['HOUR']):02d}h  "
                     f"{r['flights_per_day']:6.1f} flights/day  "
                     f"{100 * r['delay_share']:5.1f}% delayed")
    return "\n".join(lines)
