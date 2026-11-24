"""
Measure the total CSV dataset size on disk and,
estimate its memory footprint when loaded into pandas.

Usage (from the repository root):

    python tests/measure_data_size.py

Optional in-memory analysis:

    python tests/measure_data_size.py --in-memory
"""

import argparse
import calendar
import os
import sys
from pathlib import Path


# 1. CONFIGURATION

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DATA_DIR = Path(
    os.environ.get(
        "FLIGHT_DATA_DIR",
        PROJECT_ROOT / "data" / "OSPC_Flight_Data" / "raw"
    )
).expanduser()


# 2. MAIN

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--data-dir", type=Path, default=DEFAULT_DATA_DIR
    )

    parser.add_argument("--months", type=int, default=132)
    parser.add_argument("--first-year", type=int, default=2015)
    parser.add_argument("--last-year", type=int, default=2025)

    parser.add_argument(
        "--in-memory",
        action="store_true",
        help="Also estimate the pandas memory footprint"
    )

    args = parser.parse_args()

    data_dir = args.data_dir.expanduser()

    files = [
        data_dir / str(year) /
        f"BTS_Flights_{calendar.month_name[month]}_{year}.csv"
        for year in range(args.first_year, args.last_year + 1)
        for month in range(1, 13)
    ]

    if not 1 <= args.months <= len(files):
        parser.error("Invalid number of months")

    files = files[:args.months]

    missing = [path for path in files if not path.is_file()]

    if missing:
        raise FileNotFoundError(
            "Missing datasets:\n" +
            "\n".join(str(path) for path in missing)
        )

    # 3. CSV SIZE ON DISK

    csv_bytes = sum(path.stat().st_size for path in files)

    print("=" * 55)
    print("DATASET SIZE REPORT")
    print("=" * 55)

    print(f"CSV files: {len(files)}")
    print(f"Total bytes: {csv_bytes:,}")
    print(f"Dataset size: {csv_bytes / 10**9:.3f} GB")
    print(f"Dataset size: {csv_bytes / 2**30:.3f} GiB")

    # 4. OPTIONAL IN-MEMORY SIZE ESTIMATION

    if args.in_memory:

        sys.path.insert(0, str(PROJECT_ROOT / "jobs"))

        import baseline_congestion as old
        import baseline_congestion2 as new

        old_bytes = new_bytes = rows = 0

        for path in files:

            old_bytes += (
                old.read_month(path)
                .memory_usage(deep=True)
                .sum()
            )

            df = new.read_month(path)

            new_bytes += df.memory_usage(deep=True).sum()
            rows += len(df)

            del df

        print("\nESTIMATED IN-MEMORY FOOTPRINT")
        print("-" * 55)

        print(f"Flights: {rows:,}")

        print(
            f"Old version (5 columns): "
            f"{old_bytes / 2**20:.2f} MiB"
        )

        print(
            f"New version (14 columns): "
            f"{new_bytes / 2**20:.2f} MiB"
        )

    print("=" * 55)


if __name__ == "__main__":
    main()
