#!/usr/bin/env python3
"""
Sequential baseline: congestion and departure delays by airport and hour.

Usage (from the repo root):
    python scripts/baseline.py --data-dir data/raw --months 1
    python scripts/baseline.py --data-dir data/raw --months 36 --out results/baseline_36.csv

Prints one timing line (CSV-friendly) and writes the result table.
Reading/parsing time and computation time are measured separately.
"""
import argparse
import os
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flights_common as fc  # noqa: E402


def run(data_dir, n_months):
    files = fc.list_month_files(data_dir, n_months)
    t_read = t_compute = 0.0
    partials = []
    for f in files:
        t0 = time.perf_counter()
        df = fc.read_month(f)
        t1 = time.perf_counter()
        partials.append(fc.compute_partial(df))
        t2 = time.perf_counter()
        t_read += t1 - t0
        t_compute += t2 - t1
    t0 = time.perf_counter()
    result = fc.finalize(fc.combine(partials))
    t_compute += time.perf_counter() - t0
    return result, t_read, t_compute


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", default="data/raw")
    p.add_argument("--months", type=int, default=None, help="size parameter (default: all)")
    p.add_argument("--out", default=None, help="CSV file for the result table")
    p.add_argument("--quiet", action="store_true", help="do not print the summary")
    args = p.parse_args()

    t0 = time.perf_counter()
    result, t_read, t_compute = run(args.data_dir, args.months)
    t_total = time.perf_counter() - t0

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(args.out, index=False)
    if not args.quiet:
        print(fc.summary(result))

    n = args.months or len(fc.list_month_files(args.data_dir))
    print("version,workers,months,read_s,compute_s,total_s,node,job_id")
    print(f"baseline,1,{n},{t_read:.2f},{t_compute:.2f},{t_total:.2f},"
          f"{socket.gethostname()},{os.environ.get('SLURM_JOB_ID', 'local')}")


if __name__ == "__main__":
    main()
