# OSPC Parallel Data Analytics

Group project for Operating Systems and Parallel Computing.

**Project organisation:**

| Folder / File | Purpose |
|---|---|
| `data/` | Stores the datasets used for the project, including real or synthetic data. Large datasets are kept on the HPC cluster rather than uploaded to GitHub. |
| `jobs/` | Contains SLURM batch scripts used to submit experiments to the HPC cluster, specifying CPU allocation, memory, and execution time. |
| `results/` | Stores experimental outputs, including execution times, memory usage, performance comparisons, and graphs. |
| `README.md` | Provides an overview of the project, its objectives, structure, setup instructions, and instructions for reproducing the experiments. |

## Dataset

This project uses the **Bureau of Transportation Statistics (BTS)
Reporting Carrier On-Time Performance dataset**.

- **Source:** [Bureau of Transportation Statistics](https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FGJ)
- **Period:** January 2015 – December 2025
- **Files:** 132 monthly CSV files
- **Variables:** 36 selected flight-related variables
- **Format:** CSV

### Option 1: Download the prepared dataset (Recommended)

To avoid downloading each monthly file individually, we provide
the complete dataset as a compressed ZIP file.

https://drive.google.com/file/d/17y1GW_BVLtHeb0Dhkov_tGOPv0usQ9xG/view?usp=sharing

Download and extract the ZIP file into the `data/` directory
of the cloned repository.

The resulting directory structure should look like:

```text
Groupwork_Parrallel_Data_Analytics/
│
├── data/
│   ├── download_flights.py
│   └── OSPC_Flight_Data/
│       └── raw/
│           ├── 2015/
│           ├── 2016/
│           ├── ...
│           └── 2025/
├── jobs/
├── tests/
├── .gitignore
└── README.md
```

### Option 2: Download the data automatically

Alternatively, reproduce the data collection process directly
from the official BTS website:

```bash
python data/download_flights.py
```

## Running the Project

All commands must be executed from the root directory of
the cloned repository.

### Step 1: Navigate to the project directory

```bash
cd Groupwork_Parrallel_Data_Analytics
```

### Step 2: Validate the dataset

Before running the analysis, verify that all 132 monthly
CSV files from 2015 to 2025 are present and correctly formatted.

```bash
python -m pytest tests/test_data.py -v
```

The expected result is:

```text
396 passed
```

### Step 3: Measure the dataset size

To verify the total size of the CSV dataset on disk, run:

```bash
python tests/measure_data_size.py
```

To additionally estimate the in-memory footprint of both
baseline implementations, run:

```bash
python tests/measure_data_size.py --in-memory
```

#### Measured results

| Metric | Result |
|---|---:|
| Dataset period | 2015–2025 |
| Monthly CSV files | 132 |
| Flights reported | 70,081,045 |
| Total bytes | 13,156,659,351 |
| Dataset size (GB) | 13.157 GB |
| Dataset size (GiB) | 12.253 GiB |
| Estimated memory footprint (5 columns) | 1,006.13 MiB |
| Estimated memory footprint (14 columns) | 3,011.33 MiB |

The in-memory footprint is calculated by summing the
memory usage of each monthly DataFrame using pandas
`memory_usage(deep=True)`.

These values represent cumulative estimated DataFrame
memory usage, not the peak memory consumption of the
running program.

#### Workload size criterion (Section 3.1)

The project follows the memory-based workload criterion
specified in the project brief.

The complete CSV dataset occupies 12.253 GiB on disk.
The sequential baseline processes the data month by month,
allowing it to process a dataset larger than the memory
allocated to its Slurm job.

The final memory allocation and measured peak memory
usage will be documented alongside the benchmark results.
