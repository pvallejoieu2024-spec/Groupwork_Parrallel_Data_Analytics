"""
Measure how much memory the data would take if it were all loaded at once.

Usage (from the repo root):
    python scripts/measure_data_size.py --data-dir ~/Desktop/OSPC_Flight_Data/raw --months 36
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jobs"))
import baseline_congestion as old      # 5 columns
import baseline_congestion2 as new     # 14 columns


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--months", type=int, default=36)
    parser.add_argument("--first-year", type=int, default=2023)
    parser.add_argument("--last-year", type=int, default=2025)
    args = parser.parse_args()

    files = new.list_month_files(
        args.data_dir.expanduser(), args.months,
        args.first_year, args.last_year
    )

    old_bytes = new_bytes = rows = 0

    # Read one month at a time and add up its size in memory
    # (deep=True also counts the text columns, not just the numbers)
    for path in files:
        old_bytes += old.read_month(path).memory_usage(deep=True).sum()
        df = new.read_month(path)
        new_bytes += df.memory_usage(deep=True).sum()
        rows += len(df)

    print(f"Months: {args.months}   Flights: {rows:,}")
    print(f"Old version (5 columns):  {old_bytes / 2**20:7.0f} MiB")
    print(f"New version (14 columns): {new_bytes / 2**20:7.0f} MiB")


if __name__ == "__main__":
    main()