"""
Parallel version 1: process pool (one month = one task).

Same analysis as jobs/baseline_congestion2.py. The only difference is HOW
the months are processed: instead of one after another, a pool of worker
processes reads and reduces several months at the same time. The monthly
tables are then added up exactly as in the baseline.

All the analysis code is imported from the baseline, so both versions
compute exactly the same thing.

Usage:
    python jobs/parallel_pool.py --months 36 --workers 8 --repetition 1
"""

import argparse
import datetime
import os
import resource
import socket
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import baseline_congestion2 as base  # noqa: E402


def work_on_month(path):
    """Task run by one worker: read one month and reduce it to small tables."""

    read_start = time.perf_counter()
    df = base.read_month(path)
    read_s = time.perf_counter() - read_start

    compute_start = time.perf_counter()
    partial = base.process_month(df)
    compute_s = time.perf_counter() - compute_start

    return partial, read_s, compute_s


def run_pool(files, workers):
    """Run the analysis with a pool of worker processes."""

    total_start = time.perf_counter()

    # Overhead we measure directly: starting the worker processes
    start = time.perf_counter()
    pool = ProcessPoolExecutor(max_workers=workers)
    # Submitting one empty task per worker forces all of them to start now
    list(pool.map(int, range(workers)))
    pool_start_s = time.perf_counter() - start

    # chunksize=1: each month is a separate task, so a worker that finishes
    # early takes the next month (36 months do not split evenly over 32)
    work_start = time.perf_counter()
    outputs = list(pool.map(work_on_month, files, chunksize=1))
    work_s = time.perf_counter() - work_start
    pool.shutdown()

    partials = [p for p, _, _ in outputs]

    combine_start = time.perf_counter()
    results, corr = base.finalize(base.combine(partials))
    combine_s = time.perf_counter() - combine_start

    total_s = time.perf_counter() - total_start

    times = {
        # read and compute: summed over all workers (CPU work, not wall time)
        "read_s": round(sum(r for _, r, _ in outputs), 3),
        "compute_s": round(sum(c for _, _, c in outputs), 3),
        "pool_start_s": round(pool_start_s, 3),
        "work_s": round(work_s, 3),        # wall time of the parallel part
        "combine_s": round(combine_s, 3),
        "total_s": round(total_s, 3),      # wall time of everything
    }
    return results, corr, times


def peak_memory_mib():
    """Peak memory of the main process and of the largest worker, in MiB."""

    own = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    child = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    scale = 2**20 if sys.platform == "darwin" else 2**10
    return round(own / scale, 1), round(child / scale, 1)


def main():
    parser = argparse.ArgumentParser(description="Process-pool congestion analysis")
    parser.add_argument("--data-dir", type=Path, default=base.DEFAULT_DATA_DIR)
    parser.add_argument("--first-year", type=int, default=base.FIRST_YEAR)
    parser.add_argument("--last-year", type=int, default=base.LAST_YEAR)
    parser.add_argument("--months", type=int, default=132)
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--repetition", type=int, default=1)
    parser.add_argument("--results-dir", type=Path, default=base.PROJECT_ROOT / "results")
    args = parser.parse_args()

    files = base.list_month_files(
        args.data_dir.expanduser(), args.months, args.first_year, args.last_year
    )

    results, corr, times = run_pool(files, args.workers)
    main_mem, worker_mem = peak_memory_mib()

    args.results_dir.mkdir(parents=True, exist_ok=True)
    base.save_timing(args.results_dir / "timings_pool.csv", {
        "version": "pool",
        "workers": args.workers,
        "months": args.months,
        "repetition": args.repetition,
        **times,
        "peak_mem_main_mib": main_mem,
        "peak_mem_worker_mib": worker_mem,
        "node": socket.gethostname(),
        "job_id": os.environ.get("SLURM_JOB_ID", "local"),
        "load_1min": round(os.getloadavg()[0], 2),
        "date": datetime.datetime.now().isoformat(timespec="seconds"),
    })

    print(f"pool  workers={args.workers:>2}  months={args.months}  "
          f"rep={args.repetition}  total={times['total_s']:.2f}s  "
          f"(start workers {times['pool_start_s']:.2f}s, "
          f"parallel part {times['work_s']:.2f}s)")


if __name__ == "__main__":
    main()
