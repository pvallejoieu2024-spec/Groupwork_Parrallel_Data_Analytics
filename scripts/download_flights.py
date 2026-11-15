"""Download BTS flight data (2023-2025) as 36 monthly, 36-column CSVs.

Run `python3 download_flights.py --test` to download only January 2024.
Run `python3 download_flights.py` to download all months.
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


BASE_URL = (
    "https://www.transtats.bts.gov/PREZIP/"
    "On_Time_Reporting_Carrier_On_Time_Performance_1987_present"
)

COLUMNS = [
    "YEAR", "MONTH", "DAY_OF_MONTH", "DAY_OF_WEEK", "FL_DATE",
    "OP_UNIQUE_CARRIER", "TAIL_NUM", "OP_CARRIER_FL_NUM",
    "ORIGIN_AIRPORT_ID", "ORIGIN", "ORIGIN_CITY_NAME",
    "DEST_AIRPORT_ID", "DEST", "DEST_CITY_NAME",
    "CRS_DEP_TIME", "DEP_TIME", "DEP_DELAY", "DEP_DELAY_NEW",
    "DEP_DEL15", "TAXI_OUT", "TAXI_IN", "CRS_ARR_TIME", "ARR_TIME",
    "ARR_DELAY", "ARR_DELAY_NEW", "ARR_DEL15", "CANCELLED",
    "CANCELLATION_CODE", "DIVERTED", "CRS_ELAPSED_TIME", "DISTANCE",
    "CARRIER_DELAY", "WEATHER_DELAY", "NAS_DELAY", "SECURITY_DELAY",
    "LATE_AIRCRAFT_DELAY",
]

# The pre-zipped BTS files use the website's mixed-case names, whereas
# customized TranStats exports use these uppercase names.
PREZIP_NAMES = {
    "DAY_OF_MONTH": "DayofMonth", "DAY_OF_WEEK": "DayOfWeek",
    "FL_DATE": "FlightDate", "OP_UNIQUE_CARRIER": "Reporting_Airline",
    "TAIL_NUM": "Tail_Number", "OP_CARRIER_FL_NUM": "Flight_Number_Reporting_Airline",
    "ORIGIN_AIRPORT_ID": "OriginAirportID", "ORIGIN_CITY_NAME": "OriginCityName",
    "DEST_AIRPORT_ID": "DestAirportID", "DEST_CITY_NAME": "DestCityName",
    "CRS_DEP_TIME": "CRSDepTime", "DEP_TIME": "DepTime",
    "DEP_DELAY": "DepDelay", "DEP_DELAY_NEW": "DepDelayMinutes",
    "DEP_DEL15": "DepDel15", "TAXI_OUT": "TaxiOut", "TAXI_IN": "TaxiIn",
    "CRS_ARR_TIME": "CRSArrTime", "ARR_TIME": "ArrTime",
    "ARR_DELAY": "ArrDelay", "ARR_DELAY_NEW": "ArrDelayMinutes",
    "ARR_DEL15": "ArrDel15", "CANCELLATION_CODE": "CancellationCode",
    "CRS_ELAPSED_TIME": "CRSElapsedTime", "CARRIER_DELAY": "CarrierDelay",
    "WEATHER_DELAY": "WeatherDelay", "NAS_DELAY": "NASDelay",
    "SECURITY_DELAY": "SecurityDelay", "LATE_AIRCRAFT_DELAY": "LateAircraftDelay",
}


def normalize(name: str) -> str:
    return "".join(c.lower() for c in name if c.isalnum())


def download_month(output_root: Path, year: int, month: int) -> None:
    month_name = calendar.month_name[month]
    destination = output_root / str(year) / f"BTS_Flights_{month_name}_{year}.csv"
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.is_file() and destination.stat().st_size > 0:
        print(f"SKIP: {destination.name} already exists")
        return

    url = f"{BASE_URL}_{year}_{month}.zip"
    temporary = destination.with_suffix(".csv.part")
    print(f"Downloading {month_name} {year}...", flush=True)

    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=180) as response:
            with zipfile.ZipFile(io.BytesIO(response.read())) as archive:
                csv_names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
                if not csv_names:
                    raise ValueError("The ZIP contains no CSV file")

                with archive.open(csv_names[0]) as zipped_csv:
                    with io.TextIOWrapper(zipped_csv, encoding="utf-8-sig", newline="") as source:
                        reader = csv.DictReader(source)
                        available = {normalize(name): name for name in (reader.fieldnames or [])}
                        source_names = {
                            col: available.get(normalize(col))
                            or available.get(normalize(PREZIP_NAMES.get(col, col)))
                            for col in COLUMNS
                        }
                        missing = [col for col, name in source_names.items() if name is None]
                        if missing:
                            raise ValueError(f"Missing columns: {missing}; ZIP headers: {reader.fieldnames}")

                        with temporary.open("w", encoding="utf-8", newline="") as target:
                            writer = csv.DictWriter(target, fieldnames=COLUMNS)
                            writer.writeheader()
                            count = 0
                            for row in reader:
                                writer.writerow({col: row[source_names[col]] for col in COLUMNS})
                                count += 1

        if count == 0:
            raise ValueError("The CSV contains no flight records")
        temporary.replace(destination)
        print(f"OK: {destination} ({count:,} flights)", flush=True)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true", help="Download January 2024 only")
    args = parser.parse_args()
    output_root = Path(__file__).resolve().parent / "raw"
    months = [(2024, 1)] if args.test else [
        (year, month) for year in (2023, 2024, 2025) for month in range(1, 13)
    ]

    failed = []
    for year, month in months:
        for attempt in range(1, 4):
            try:
                download_month(output_root, year, month)
                break
            except (urllib.error.URLError, TimeoutError, OSError, ValueError, zipfile.BadZipFile) as error:
                print(f"Attempt {attempt}/3 failed for {year}-{month:02d}: {error}", flush=True)
                if attempt < 3:
                    time.sleep(3 * attempt)
                else:
                    failed.append(f"{year}-{month:02d}")

    if failed:
        print("Failed months (rerun the script to retry): " + ", ".join(failed))
        raise SystemExit(1)
    print("Done! All requested months are ready.")


if __name__ == "__main__":
    main()
