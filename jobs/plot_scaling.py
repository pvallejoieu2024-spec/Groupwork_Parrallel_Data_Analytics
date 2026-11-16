"""
Strong-scaling plot of the process-pool version.

Reads results/timings_pool.csv (one row per run) and, if present, the
baseline v2 runs in results/v2/timings.csv. Saves results/strong_scaling_pool.png
and prints the table (median, min, max, speedup, efficiency).

Usage:
    python jobs/plot_scaling.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

RESULTS = Path(__file__).resolve().parents[1] / "results"
MONTHS = 36

pool = pd.read_csv(RESULTS / "timings_pool.csv")
pool = pool[pool["months"] == MONTHS]

table = (pool.groupby("workers")["total_s"]
         .agg(["median", "min", "max", "count"]).sort_index())
reference = table.loc[1, "median"]
table["speedup"] = reference / table["median"]
table["efficiency"] = table["speedup"] / table.index
print(table.round(3))

baseline_file = RESULTS / "v2" / "timings.csv"
baseline_median = None
if baseline_file.exists():
    base = pd.read_csv(baseline_file)
    base = base[(base["version"] == "baseline") & (base["months"] == MONTHS)]
    if len(base):
        baseline_median = base["total_s"].median()
        print(f"\nSequential baseline median: {baseline_median:.2f} s")

w = table.index
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))

ax1.errorbar(w, table["median"],
             yerr=[table["median"] - table["min"], table["max"] - table["median"]],
             marker="o", capsize=4, label="Process pool (median, min-max)")
if baseline_median is not None:
    ax1.axhline(baseline_median, color="grey", linestyle=":",
                label="Sequential baseline")
ax1.set(xscale="log", xlabel="Workers", ylabel="Run time (s)",
        title=f"Run time, {MONTHS} months")
ax1.set_xticks(w, [str(x) for x in w])
ax1.legend()

ax2.plot(w, table["speedup"], marker="o", label="Measured")
ax2.plot(w, w, linestyle="--", color="grey", label="Ideal")
ax2.set(xscale="log", yscale="log", xlabel="Workers",
        ylabel="Speedup vs 1 worker", title="Speedup")
ax2.set_xticks(w, [str(x) for x in w])
ax2.set_yticks(w, [str(x) for x in w])
ax2.legend()

fig.tight_layout()
out = RESULTS / "strong_scaling_pool.png"
fig.savefig(out, dpi=150)
print(f"\nSaved {out}")
