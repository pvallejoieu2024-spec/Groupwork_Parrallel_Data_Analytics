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

#### Step 1: Extract the dataset

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

### **Running the Project**

All commands must be executed from the root directory of
the cloned repository.

#### Step 1: Navigate to the project directory

```bash
cd Groupwork_Parrallel_Data_Analytics
```

#### Step 2: Validate the dataset

Before running the analysis, verify that all 132 monthly
CSV files from 2015 to 2025 are present and correctly formatted.

```bash
python -m pytest tests/test_data.py -v
```

The expected result is:

```text
396 passed
```

#### Step 3: Run the sequential baseline

```bash
python jobs/baseline_congestion2.py
```

The scripts automatically locate the dataset in:

```text
data/OSPC_Flight_Data/raw/
```

No manual path modifications or environment variable
configuration are required when the recommended directory
structure is followed.

