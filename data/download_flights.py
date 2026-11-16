"""
Download BTS flight data (2015–2025) as monthly, 36-column CSV files.

Dataset:
    US Bureau of Transportation Statistics (BTS)
    Reporting Carrier On-Time Performance

Period:
    January 2015 – December 2025
    11 years = 132 months

Usage (from repository root):

    # Test January 2015
    python3 data/download_flights.py --test

    # Download all months from 2015 to 2025
    python3 data/download_flights.py

    # Download only selected years
    python3 data/download_flights.py --start-year 2015 --end-year 2017

Output:
    data/raw/2015/BTS_Flights_January_2015.csv
    data/raw/2015/BTS_Flights_February_2015.csv
    ...
    data/raw/2025/BTS_Flights_December_2025.csv

Notes:
    - Existing nonempty files are skipped.
    - Raw data should NOT be committed to GitHub.
    - The data directory should be included in .gitignore.
"""

import argparse
import calendar
import csv
import io
import time
import urllib.error
import urllib.request
import zipfile

from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

START_YEAR = 2015
END_YEAR = 2025

BASE_URL = (
    "https://www.transtats.bts.gov/PREZIP/"
    "On_Time_Reporting_Carrier_On_Time_Performance_1987_present"
)


# ============================================================
# SELECTED COLUMNS
# ============================================================

COLUMNS = [
    "YEAR",
    "MONTH",
    "DAY_OF_MONTH",
    "DAY_OF_WEEK",
    "FL_DATE",
    "OP_UNIQUE_CARRIER",
    "TAIL_NUM",
    "OP_CARRIER_FL_NUM",
    "ORIGIN_AIRPORT_ID",
    "ORIGIN",
    "ORIGIN_CITY_NAME",
    "DEST_AIRPORT_ID",
    "DEST",
    "DEST_CITY_NAME",
    "CRS_DEP_TIME",
    "DEP_TIME",
    "DEP_DELAY",
    "DEP_DELAY_NEW",
    "DEP_DEL15",
    "TAXI_OUT",
    "TAXI_IN",
    "CRS_ARR_TIME",
    "ARR_TIME",
    "ARR_DELAY",
    "ARR_DELAY_NEW",
    "ARR_DEL15",
    "CANCELLED",
    "CANCELLATION_CODE",
    "DIVERTED",
    "CRS_ELAPSED_TIME",
    "DISTANCE",
    "CARRIER_DELAY",
    "WEATHER_DELAY",
    "NAS_DELAY",
    "SECURITY_DELAY",
    "LATE_AIRCRAFT_DELAY",
]


# ============================================================
# BTS COLUMN NAME MAPPING
# ============================================================

PREZIP_NAMES = {
    "DAY_OF_MONTH": "DayofMonth",
    "DAY_OF_WEEK": "DayOfWeek",
    "FL_DATE": "FlightDate",
    "OP_UNIQUE_CARRIER": "Reporting_Airline",
    "TAIL_NUM": "Tail_Number",
    "OP_CARRIER_FL_NUM": "Flight_Number_Reporting_Airline",
    "ORIGIN_AIRPORT_ID": "OriginAirportID",
    "ORIGIN_CITY_NAME": "OriginCityName",
    "DEST_AIRPORT_ID": "DestAirportID",
    "DEST_CITY_NAME": "DestCityName",
    "CRS_DEP_TIME": "CRSDepTime",
    "DEP_TIME": "DepTime",
    "DEP_DELAY": "DepDelay",
    "DEP_DELAY_NEW": "DepDelayMinutes",
    "DEP_DEL15": "DepDel15",
    "TAXI_OUT": "TaxiOut",
    "TAXI_IN": "TaxiIn",
    "CRS_ARR_TIME": "CRSArrTime",
    "ARR_TIME": "ArrTime",
    "ARR_DELAY": "ArrDelay",
    "ARR_DELAY_NEW": "ArrDelayMinutes",
    "ARR_DEL15": "ArrDel15",
    "CANCELLATION_CODE": "CancellationCode",
    "CRS_ELAPSED_TIME": "CRSElapsedTime",
    "CARRIER_DELAY": "CarrierDelay",
    "WEATHER_DELAY": "WeatherDelay",
    "NAS_DELAY": "NASDelay",
    "SECURITY_DELAY": "SecurityDelay",
    "LATE_AIRCRAFT_DELAY": "LateAircraftDelay",
}


# Additional historical column names
ALTERNATIVE_NAMES = {
    "OP_UNIQUE_CARRIER": [
        "UniqueCarrier",
        "Reporting_Airline",
        "OP_UNIQUE_CARRIER",
    ],
    "OP_CARRIER_FL_NUM": [
        "FlightNum",
        "Flight_Number_Reporting_Airline",
        "OP_CARRIER_FL_NUM",
    ],
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def normalize(name: str) -> str:
    """Normalize a column name for comparison."""
    return "".join(
        character.lower()
        for character in name
        if character.isalnum()
    )


def get_source_column(column, available):
    """Find the matching BTS column name."""

    candidates = [
        column,
        PREZIP_NAMES.get(column, column),
    ]

    candidates.extend(ALTERNATIVE_NAMES.get(column, []))

    for candidate in candidates:
        match = available.get(normalize(candidate))

        if match is not None:
            return match

    return None


# ============================================================
# DOWNLOAD ONE MONTH
# ============================================================

def download_month(output_root: Path, year: int, month: int) -> int:
    """
    Download and convert one monthly BTS dataset.

    Returns:
        Number of downloaded flights.
        Returns 0 when the file already exists.
    """

    month_name = calendar.month_name[month]

    destination = (
        output_root
        / str(year)
        / f"BTS_Flights_{month_name}_{year}.csv"
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # Skip already downloaded files
    if destination.is_file() and destination.stat().st_size > 0:
        print(
            f"SKIP: {destination.name} already exists",
            flush=True
        )
        return 0

    url = f"{BASE_URL}_{year}_{month}.zip"

    temporary = destination.with_suffix(".csv.part")

    print(
        f"Downloading {month_name} {year}...",
        flush=True
    )

    try:

        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        with urllib.request.urlopen(
            request,
            timeout=180
        ) as response:

            with zipfile.ZipFile(
                io.BytesIO(response.read())
            ) as archive:

                csv_names = [
                    name
                    for name in archive.namelist()
                    if name.lower().endswith(".csv")
                ]

                if not csv_names:
                    raise ValueError(
                        "The ZIP contains no CSV file"
                    )

                with archive.open(csv_names[0]) as zipped_csv:

                    with io.TextIOWrapper(
                        zipped_csv,
                        encoding="utf-8-sig",
                        newline=""
                    ) as source:

                        reader = csv.DictReader(source)

                        available = {
                            normalize(name): name
                            for name in (reader.fieldnames or [])
                        }

                        source_names = {
                            column: get_source_column(
                                column,
                                available
                            )
                            for column in COLUMNS
                        }

                        missing = [
                            column
                            for column, name in source_names.items()
                            if name is None
                        ]

                        if missing:
                            raise ValueError(
                                f"Missing columns: {missing}\n"
                                f"Available BTS columns: "
                                f"{reader.fieldnames}"
                            )

                        with temporary.open(
                            "w",
                            encoding="utf-8",
                            newline=""
                        ) as target:

                            writer = csv.DictWriter(
                                target,
                                fieldnames=COLUMNS
                            )

                            writer.writeheader()

                            count = 0

                            for row in reader:

                                writer.writerow({
                                    column: row[source_names[column]]
                                    for column in COLUMNS
                                })

                                count += 1

        if count == 0:
            raise ValueError(
                "The CSV contains no flight records"
            )

        # Only save the final file after successful conversion
        temporary.replace(destination)

        print(
            f"OK: {destination.name} "
            f"({count:,} flights)",
            flush=True
        )

        return count

    finally:

        if temporary.exists():
            temporary.unlink()


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="Download January 2015 only"
    )

    parser.add_argument(
        "--start-year",
        type=int,
        default=START_YEAR,
        help="First year to download (default: 2015)"
    )

    parser.add_argument(
        "--end-year",
        type=int,
        default=END_YEAR,
        help="Last year to download (default: 2025)"
    )

    args = parser.parse_args()

    if args.start_year > args.end_year:
        parser.error(
            "--start-year cannot be greater than --end-year"
        )

    output_root = (
        Path(__file__).resolve().parent / "raw"
    )

    # Select months
    if args.test:

        months = [(2015, 1)]

    else:

        months = [
            (year, month)
            for year in range(
                args.start_year,
                args.end_year + 1
            )
            for month in range(1, 13)
        ]

    print("=" * 55)
    print("BTS FLIGHT DATA DOWNLOADER")
    print("=" * 55)

    print(f"Output directory: {output_root}")
    print(f"Months requested: {len(months)}")
    print(f"Selected columns: {len(COLUMNS)}")

    print("=" * 55)

    failed = []
    downloaded_flights = 0

    start_time = time.perf_counter()

    # Download each month
    for year, month in months:

        for attempt in range(1, 4):

            try:

                count = download_month(
                    output_root,
                    year,
                    month
                )

                downloaded_flights += count

                break

            except (
                urllib.error.URLError,
                TimeoutError,
                OSError,
                ValueError,
                zipfile.BadZipFile
            ) as error:

                print(
                    f"Attempt {attempt}/3 failed "
                    f"for {year}-{month:02d}: {error}",
                    flush=True
                )

                if attempt < 3:
                    time.sleep(3 * attempt)

                else:
                    failed.append(
                        f"{year}-{month:02d}"
                    )

    elapsed = time.perf_counter() - start_time

    # Final summary
    print()
    print("=" * 55)
    print("DOWNLOAD SUMMARY")
    print("=" * 55)

    print(f"Months requested: {len(months)}")
    print(f"New flights downloaded: {downloaded_flights:,}")
    print(f"Elapsed time: {elapsed:.2f} seconds")
    print(f"Failed months: {len(failed)}")

    if failed:

        print()
        print("Failed months:")

        for month in failed:
            print(f"  - {month}")

        print()
        print("Rerun the script to retry failed months.")

        raise SystemExit(1)

    print()
    print("SUCCESS: All requested months are ready!")


if __name__ == "__main__":
    main()
