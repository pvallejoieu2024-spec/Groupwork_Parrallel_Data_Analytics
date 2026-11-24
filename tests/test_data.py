from pathlib import Path
import calendar
import csv
import os
import pytest


# 1. CONFIGURATION - so the code can be reproducible

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = Path(
    os.environ.get(
        "FLIGHT_DATA_DIR",
        PROJECT_ROOT / "data" / "OSPC_Flight_Data" / "raw"
    )
).expanduser()

# Data we are using 
YEARS = range(2015, 2026)
MONTHS = range(1, 13)

MONTHLY_PERIODS = [
    (year, month)
    for year in YEARS
    for month in MONTHS
]

REQUIRED_COLUMNS = {
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
}


# 2. HELPER FUNCTION 

def get_filepath(year, month):

    month_name = calendar.month_name[month]
    filename = f"BTS_Flights_{month_name}_{year}.csv"

    return DATA_DIR / str(year) / filename


# 3. TEST FILE EXISTENCE

@pytest.mark.parametrize("year,month", MONTHLY_PERIODS)
def test_files_exist(year, month):

    filepath = get_filepath(year, month)

    assert filepath.is_file(), (
        f"Missing file: {filepath}"
    )

    assert filepath.stat().st_size > 0, (
        f"Empty file: {filepath}"
    )


# 4. TEST REQUIRED COLUMNS

@pytest.mark.parametrize("year,month", MONTHLY_PERIODS)
def test_required_columns(year, month):

    filepath = get_filepath(year, month)

    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        columns = next(reader)

    assert len(columns) == len(REQUIRED_COLUMNS), (
        f"{filepath.name}: Expected {len(REQUIRED_COLUMNS)} "
        f"columns, found {len(columns)}"
    )

    missing_columns = REQUIRED_COLUMNS - set(columns)

    assert not missing_columns, (
        f"{filepath.name}: Missing columns: {missing_columns}"
    )


# 5. TEST CORRECT PERIOD

@pytest.mark.parametrize("year,month", MONTHLY_PERIODS)
def test_correct_period(year, month):

    filepath = get_filepath(year, month)

    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row_number, row in enumerate(reader, start=2):

            assert int(row["YEAR"]) == year, (
                f"{filepath.name}, row {row_number}: Wrong year"
            )

            assert int(row["MONTH"]) == month, (
                f"{filepath.name}, row {row_number}: Wrong month"
            )
