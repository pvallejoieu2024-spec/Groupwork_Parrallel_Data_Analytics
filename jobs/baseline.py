import pandas as pd

# keep only the columns we need to predict departure delay

path = "/Users/nourhassine/Desktop/OSPC_Flight_Data/raw/2024/BTS_Flights_January_2024.csv"

cols = ["ORIGIN", "CRS_DEP_TIME", "DEP_DEL15", "CANCELLED"]
df = pd.read_csv(path, usecols=cols) #tells pandas to read only those columns

df["HOUR"] = df["CRS_DEP_TIME"] // 100 #to get the hour

print(df.shape)
print(df.head(10))

#remove cancelled flights because they don't have a departure delay

print("Before removing cancelled:", len(df))

df = df[df["CANCELLED"] == 0]

print("After removing cancelled:", len(df))

# grouping by airport and hour 

result = df.groupby(["ORIGIN", "HOUR"]).agg(
    n_flights=("DEP_DEL15", "count"),
    n_delayed=("DEP_DEL15", "sum"),
)

result["delay_share"] = result["n_delayed"] / result["n_flights"]

print(result.head(10))
print("Number of airport-hours:", len(result))

#most delayed airport-hours: keeping only busy ones

busy = result[result["n_flights"] >= 100]

top = busy.sort_values("delay_share", ascending=False).head(10)

print("Busy airport-hours:", len(busy))
print(top)

#looping over several months + timing it

import glob
import time
import pandas as pd

DATA_DIR = "/Users/nourhassine/Desktop/OSPC_Flight_Data/raw"
N_MONTHS = 36          # size parameter: change this to test

def process_month(path):
    cols = ["ORIGIN", "CRS_DEP_TIME", "DEP_DEL15", "CANCELLED"]
    df = pd.read_csv(path, usecols=cols)
    df["HOUR"] = df["CRS_DEP_TIME"] // 100
    df = df[df["CANCELLED"] == 0]
    return df.groupby(["ORIGIN", "HOUR"]).agg(
        n_flights=("DEP_DEL15", "count"),
        n_delayed=("DEP_DEL15", "sum"),
    )

files = sorted(glob.glob(f"{DATA_DIR}/*/*.csv"))[:N_MONTHS]

start = time.perf_counter()

partials = [process_month(f) for f in files]
result = pd.concat(partials).groupby(["ORIGIN", "HOUR"]).sum()
result["delay_share"] = result["n_delayed"] / result["n_flights"]

elapsed = time.perf_counter() - start

busy = result[result["n_flights"] >= 100]
print(busy.sort_values("delay_share", ascending=False).head(10))
print(f"{N_MONTHS} months processed in {elapsed:.2f} seconds")

