"""
Strong-scaling analysis of the process pool, against the sequential baseline.

It reads the jobs listed in ONE submission file written by
jobs/submit_pool_scaling.sh (results/submissions/<stamp>_<node>_r<reps>.csv),
so old runs and pilot runs are never mixed in:

    single_worker job  ->  results/single_worker/<JOB_ID>/timings.csv       (baseline)
                           results/single_worker/<JOB_ID>/timings_pool.csv  (pool, 1 worker)
    pool jobs          ->  results/pool/<JOB_ID>/timings_pool.csv           (pool, W workers)

What it computes, per number of workers W (median of the repetitions):
    speedup     = median time of the SEQUENTIAL BASELINE / median time with W workers
    efficiency  = speedup / W
    Karp-Flatt  = experimentally determined serial fraction
                  e = (1/speedup - 1/W) / (1 - 1/W)        (W > 1)
and, separately, the overhead of the pool with 1 worker compared with the
baseline, measured in the same job with the same resources.
It also fits Amdahl's Law, speedup(W) = 1 / (f + (1 - f) / W), to the
measured speedups to estimate the serial fraction f.

Outputs (tracked in Git):
    results/scaling/<submission>_summary.csv
    results/scaling/<submission>.png

Usage (from the repository root):
    python jobs/plot_scaling.py                      # latest submission with >= 5 repetitions
    python jobs/plot_scaling.py --submission results/submissions/<file>.csv
"""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def latest_submission(min_reps):
    files = sorted((RESULTS / "submissions").glob("*.csv"))
    files = [f for f in files if pd.read_csv(f)["repetitions"].iloc[0] >= min_reps]
    if not files:
        raise SystemExit(f"No submission with >= {min_reps} repetitions in "
                         "results/submissions/. Use --submission <file>.")
    return files[-1]


def read_job(kind, job_id):
    folder = RESULTS / ("single_worker" if kind == "single_worker" else "pool") / str(job_id)
    frames = {}
    for name in ["timings.csv", "timings_pool.csv"]:
        if (folder / name).exists():
            frames[name] = pd.read_csv(folder / name)
    if not frames:
        print(f"  WARNING: no timings for {kind} job {job_id} in {folder} "
              "(still running, failed or not pulled?)")
    return frames


def spread(series):
    return pd.Series({"median": series.median(), "min": series.min(),
                      "max": series.max(), "runs": series.size})


def amdahl_fit(workers, speedup):
    """Serial fraction f that best fits speedup = 1 / (f + (1 - f) / W)."""
    grid = np.linspace(0, 1, 100001)
    w = np.asarray(workers, dtype=float)[:, None]
    predicted = 1 / (grid + (1 - grid) / w)
    error = ((predicted - np.asarray(speedup)[:, None]) ** 2).sum(axis=0)
    return grid[error.argmin()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path)
    parser.add_argument("--min-reps", type=int, default=5,
                        help="when choosing the latest submission automatically")
    args = parser.parse_args()

    submission = args.submission or latest_submission(args.min_reps)
    jobs = pd.read_csv(submission)
    print(f"Submission: {submission.name}  (node {jobs['node'].iloc[0]}, "
          f"{jobs['repetitions'].iloc[0]} repetition(s) per configuration)\n")

    baseline, pool_single, pool = [], [], []
    for _, job in jobs.iterrows():
        frames = read_job(job["kind"], job["job_id"])
        if job["kind"] == "single_worker":
            if "timings.csv" in frames:
                baseline.append(frames["timings.csv"])
            if "timings_pool.csv" in frames:
                pool_single.append(frames["timings_pool.csv"])
        elif "timings_pool.csv" in frames:
            pool.append(frames["timings_pool.csv"])

    if not baseline or not pool:
        raise SystemExit("Need the single-worker job (baseline) and at least one pool job.")

    baseline = pd.concat(baseline)
    pool = pd.concat(pool)
    pool_single = pd.concat(pool_single) if pool_single else None

    nodes = set(baseline["node"]) | set(pool["node"])
    if len(nodes) > 1:
        print(f"  WARNING: runs come from different nodes: {sorted(nodes)}")

    months = int(baseline["months"].iloc[0])
    csv_gb = float(baseline["csv_gb"].iloc[0])

    # --- 1. Sequential baseline and pool overhead with one worker -------------
    base = spread(baseline["total_s"])
    print(f"Sequential baseline: median {base['median']:.2f} s "
          f"(min {base['min']:.2f}, max {base['max']:.2f}, {int(base['runs'])} runs), "
          f"{months} months, {csv_gb:.3f} GB of CSV, "
          f"peak memory {baseline['peak_mem_mib'].max():.0f} MiB")

    overhead = None
    if pool_single is not None:
        one = spread(pool_single["total_s"])
        overhead = one["median"] - base["median"]
        print(f"Pool, 1 worker (same job, same resources): median {one['median']:.2f} s "
              f"-> overhead {overhead:+.2f} s ({overhead / base['median']:+.1%}); "
              f"starting the worker: median {pool_single['pool_start_s'].median():.3f} s")

    # --- 2. Strong scaling ------------------------------------------------------
    rows = []
    for workers, runs in pool.groupby("workers"):
        s = spread(runs["total_s"])
        speedup = base["median"] / s["median"]
        rows.append({
            "workers": workers,
            "runs": int(s["runs"]),
            "median_s": s["median"], "min_s": s["min"], "max_s": s["max"],
            "speedup_vs_baseline": speedup,
            "efficiency": speedup / workers,
            "karp_flatt_serial_fraction":
                (1 / speedup - 1 / workers) / (1 - 1 / workers) if workers > 1 else np.nan,
            "pool_start_s": runs["pool_start_s"].median(),
            "throughput_gb_s": runs["throughput_gb_s"].median(),
            "peak_mem_worker_mib": runs["peak_mem_worker_mib"].max(),
            "peak_mem_main_mib": runs["peak_mem_main_mib"].max(),
            "cpus_available": int(runs["cpus_available"].iloc[0]),
            "load_1min_median": runs["load_1min"].median(),
            "node": ",".join(sorted(set(runs["node"]))),
            "job_id": ",".join(str(j) for j in sorted(set(runs["job_id"]))),
        })
    table = pd.DataFrame(rows).set_index("workers")

    f = amdahl_fit(table.index, table["speedup_vs_baseline"])

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 20)
    print("\nStrong scaling (speedup against the sequential baseline):")
    print(table[["runs", "median_s", "min_s", "max_s", "speedup_vs_baseline",
                 "efficiency", "karp_flatt_serial_fraction", "throughput_gb_s",
                 "peak_mem_worker_mib", "load_1min_median"]].round(3))
    print(f"\nAmdahl fit: serial fraction f = {f:.3f} "
          f"(maximum possible speedup 1/f = {1 / f:.1f}x)" if f > 0 else
          "\nAmdahl fit: serial fraction f = 0")

    # --- 3. Save the table and the plot ----------------------------------------
    out_dir = RESULTS / "scaling"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = submission.stem
    summary = table.copy()
    summary["baseline_median_s"] = base["median"]
    summary["pool1_overhead_s"] = overhead
    summary["amdahl_serial_fraction"] = f
    summary.to_csv(out_dir / f"{stem}_summary.csv")

    w = table.index.to_numpy()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.6))

    ax1.errorbar(w, table["median_s"],
                 yerr=[table["median_s"] - table["min_s"], table["max_s"] - table["median_s"]],
                 marker="o", capsize=4, label="Process pool (median, min-max)")
    ax1.axhline(base["median"], color="grey", linestyle=":",
                label=f"Sequential baseline ({base['median']:.0f} s)")
    ax1.set(xscale="log", xlabel="Workers (1 CPU and 1 GiB each)", ylabel="Run time (s)",
            title=f"Run time, {months} months ({csv_gb:.1f} GB of CSV)")
    ax1.set_xticks(w, [str(x) for x in w])
    ax1.legend()

    fine = np.geomspace(w.min(), w.max(), 100)
    ax2.plot(w, table["speedup_vs_baseline"], marker="o", label="Measured")
    ax2.plot(w, w, linestyle="--", color="grey", label="Ideal (linear)")
    ax2.plot(fine, 1 / (f + (1 - f) / fine), linestyle=":", color="tab:red",
             label=f"Amdahl fit (f = {f:.3f})")
    for x, s, e in zip(w, table["speedup_vs_baseline"], table["efficiency"]):
        ax2.annotate(f"{e:.0%}", (x, s), textcoords="offset points", xytext=(0, 8),
                     ha="center", fontsize=8)
    ax2.set(xscale="log", yscale="log", xlabel="Workers",
            ylabel="Speedup vs sequential baseline",
            title="Speedup (labels: efficiency)")
    ax2.set_xticks(w, [str(x) for x in w])
    ax2.set_yticks(w, [str(x) for x in w])
    ax2.legend()

    fig.suptitle(f"Strong scaling of the process pool on node "
                 f"{jobs['node'].iloc[0]} ({submission.stem})", fontsize=10)
    fig.tight_layout()
    fig.savefig(out_dir / f"{stem}.png", dpi=150)
    print(f"\nSaved {out_dir / (stem + '_summary.csv')} and {out_dir / (stem + '.png')}")


if __name__ == "__main__":
    main()
