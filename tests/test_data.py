from pathlib import Path
import calendar
import pytest


# Location of the datasets on Patricia's Mac
DATA_DIR = (
    Path.home()
    / "Desktop"
    / "OSPC_Flight_Data"
    / "raw"
)

YEARS = [2023, 2024, 2025]
MONTHS = range(1, 13)


@pytest.mark.parametrize(
    "year,month",
    [
        (year, month)
        for year in YEARS
        for month in MONTHS
    ]
)
def test_files_exist(year, month):

    month_name = calendar.month_name[month]

    filename = f"BTS_Flights_{month_name}_{year}.csv"

    filepath = DATA_DIR / str(year) / filename

    assert filepath.exists(), f"Missing file: {filepath}"

    assert filepath.stat().st_size > 0, (
        f"Empty file: {filepath}"
    )

import csv

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

@pytest.mark.parametrize(
    "year,month",
    [
        (year, month)
        for year in YEARS
        for month in MONTHS
    ]
)
def test_required_columns(year, month):

    month_name = calendar.month_name[month]

    filename = f"BTS_Flights_{month_name}_{year}.csv"

    filepath = DATA_DIR / str(year) / filename

    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        columns = next(reader)

    assert len(columns) == 36, (
        f"{filename}: Expected 36 columns, found {len(columns)}"
    )


@pytest.mark.parametrize(
    "year,month",
    [
        (year, month)
        for year in YEARS
        for month in MONTHS
    ]
)
def test_correct_period(year, month):

    month_name = calendar.month_name[month]

    filename = f"BTS_Flights_{month_name}_{year}.csv"

    filepath = DATA_DIR / str(year) / filename

    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row_number, row in enumerate(reader, start=2):

            assert int(row["YEAR"]) == year, (
                f"{filename}, row {row_number}: Wrong year"
            )

            assert int(row["MONTH"]) == month, (
                f"{filename}, row {row_number}: Wrong month"
            )
