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

## Quick test (less than 5 minutes)

To check that everything works before using the cluster, run a small
configuration (2 months) from the repository root. It needs only the
January and February 2015 files.

```bash
# Correctness: the process pool must give the same results as the baseline
python tests/check_equivalence.py --months 2 --workers 2

# Sequential baseline and process pool on 2 months
python jobs/baseline_congestion2.py --months 2 --results-dir results/quick_test
python jobs/parallel_pool.py --months 2 --workers 2 --results-dir results/quick_test

# Compare the result tables saved by both versions
python tests/compare_outputs.py results/quick_test --months 2
```

The last command must end with
`PASSED: the pool output matches the baseline output.`
If your data is not in `data/OSPC_Flight_Data/raw`, add
`--data-dir <path>` to every command (or set the `FLIGHT_DATA_DIR`
environment variable).

## Experimental methodology (revised after the instructor's feedback)

### What changed and why

| Feedback | Change |
|---|---|
| The baseline had 512 MiB and the pool 24 GiB whatever the number of workers, which could favour the pool through the page cache. | Every configuration gets **1 CPU and 1 GiB of memory per worker**: baseline 1 GiB, pool with W workers W CPUs and W GiB. The job scripts stop with an error if Slurm gives a different allocation. |
| Compare the baseline and the pool with one worker under the same conditions. | `jobs/compare_single_worker_job.sh` runs both in the **same job** (1 CPU, 1 GiB), alternating which one runs first in each repetition, so neither always benefits from files already cached. |
| Speedup must use the sequential baseline as the reference. | `jobs/plot_scaling.py` divides the **median time of the sequential baseline** by the median time with W workers. The pool with one worker is reported separately, to measure the overhead of the pool. |
| Report how much data each run processes. | Every timing row records `csv_gb` (GB of CSV read, 10⁹ bytes) and `throughput_gb_s`. |
| All runs must be on the same hardware and not overlap. | `jobs/submit_pool_scaling.sh` submits every configuration to **one node** (`--nodelist`) as a **chain**: each job starts only after the previous one has finished. |
| Check the CPU topology. | Every job prints its conditions (`jobs/log_conditions.sh`): node, allocated CPU IDs, the physical core each CPU belongs to, memory, load, Git commit, Python and pandas versions. `jobs/check_node_job.sh` does the same before the experiments. |

### Files

| File | Purpose |
|---|---|
| `jobs/baseline_congestion2.py` | Sequential baseline (132 months, month by month). |
| `jobs/parallel_pool.py` | Process pool: one month per task; imports the analysis code from the baseline, so both compute the same thing. |
| `jobs/log_conditions.sh` | Prints the experimental conditions at the start of every job. |
| `jobs/check_node_job.sh` | Short job to inspect a node's CPU topology and load before the experiments. |
| `jobs/compare_single_worker_job.sh` | Baseline vs pool with 1 worker in the same job (1 CPU, 1 GiB), then checks that both outputs match on the full dataset. |
| `jobs/parallel_pool_job.sh` | Pool with W workers (W CPUs, W GiB), 5 repetitions. |
| `jobs/submit_pool_scaling.sh` | Submits the single-worker comparison and the pool with 1, 2, 4, 8, 16 and 32 workers as a chain on one node, and saves the job IDs in `results/submissions/`. |
| `jobs/plot_scaling.py` | Reads the jobs of one submission and produces the strong-scaling table and plot. |
| `tests/check_equivalence.py` | Baseline vs pool on a small input (run before every experiment). |
| `tests/compare_outputs.py` | Baseline vs pool on the result tables saved by a full run. |

### Equivalence rules

Counts and minute totals are integers and must be **exactly** equal.
Shares, means and the correlation are floating-point numbers and must be
equal within a relative tolerance of 10⁻⁹: adding the monthly results in
a different order can change only the last digits of a floating-point
sum. The correlation is saved rounded to 6 decimals, so it is compared
within 10⁻⁶.

### How to run the experiments on the cluster

All commands from the repository root, in the JupyterLab terminal.

```bash
# 0. Latest code and the full dataset (see "Dataset")
git pull --ff-only origin main
python -m pytest tests/test_data.py -q         # 396 passed

# 1. Choose a node and inspect it
sinfo -N -l                                     # nodes and their state
sbatch --nodelist=<NODE> jobs/check_node_job.sh
cat results/check-node-<JOB_ID>.out

# 2. Pilot: 1 repetition of every configuration
bash jobs/submit_pool_scaling.sh <NODE> 1
#    (one full physical core per worker instead of one hardware thread:
#     CPUS_PER_WORKER=2 bash jobs/submit_pool_scaling.sh <NODE> 1)
squeue --me                                     # wait until the chain is finished
python jobs/plot_scaling.py --submission results/submissions/<pilot file>.csv

# 3. Experiment: 5 repetitions of every configuration
bash jobs/submit_pool_scaling.sh <NODE>
python jobs/plot_scaling.py                     # uses the latest submission with 5 repetitions

# 4. Peak memory measured by Slurm for every job of the experiment
sacct -j <JOB_IDS separated by commas> --format=JobID,JobName,AllocCPUS,ReqMem,MaxRSS,Elapsed,State
```

Results are saved per job, so new runs never mix with old ones:

```text
results/
├── submissions/<date>_<node>_r<reps>_c<cpus per worker>.csv   job IDs of each submission
├── single_worker/<JOB_ID>/                    baseline + pool(1) timings and result tables
├── pool/<JOB_ID>/                             pool(W) timings and result tables
├── scaling/<submission>_summary.csv           strong-scaling table
├── scaling/<submission>.png                   strong-scaling plot
└── *.out                                      Slurm logs with the experimental conditions
```

Older files directly in `results/` (`timings.csv`, `timings_pool.csv`,
`strong_scaling_pool.png`, `congestion_*_36m.csv`) and in `results/v2/`
come from the **previous methodology** (512 MiB for the baseline and
24 GiB for the pool whatever the number of workers, speedup against the
pool with one worker). They are kept for reference only and are not used
in the revised analysis.

### Results (revised methodology)

*To be completed after the runs on the cluster.*

- Node and CPU topology (`jobs/check_node_job.sh`, job 38288, 26 Nov 2026):
  the experiments run on **julia**, which has 2 × AMD EPYC 9745
  (2 sockets × 128 cores × 2 hardware threads = 512 Slurm CPUs) and
  2 NUMA nodes. We chose julia because the JupyterLab sessions run on
  haskell, and fortran and haskell were reserved for other jobs.
  **Slurm allocates CPUs as pairs of hardware threads of the same core:**
  a job that asked for 4 CPUs got CPUs 4, 5, 260 and 261, which are only
  physical cores 4 and 5. So `--cpus-per-task=W` gives W/2 physical
  cores, and with one CPU per worker, two workers share each core.
  `CPUS_PER_WORKER=2` gives every worker its own physical core (32 workers
  = 64 CPUs, our limit). A 16-CPU GPU job of another user was also running
  on julia during this check, so every run records the load of the node.
- Pilot (1 repetition): *pending*. Does 1 GiB per worker suffice? *pending*
- Equivalence on the full dataset (132 months): *pending*
- Sequential baseline vs pool with 1 worker (overhead): *pending*
- Strong scaling, speedup against the sequential baseline: *pending*
