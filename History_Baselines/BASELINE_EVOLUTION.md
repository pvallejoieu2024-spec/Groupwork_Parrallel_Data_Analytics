# How our sequential baseline evolved

These are **three separate, commented development versions** of the BTS flight-delay baseline. They are kept here for the team to understand our design decisions, not as three parallel algorithms. Please use the main `jobs/` scripts for official experiments unless the team explicitly chooses and validates another version.

## Version 1: First working baseline
- Reads monthly CSVs one at a time, keeps four columns and groups by airport + scheduled hour.
- Counts non-cancelled flights with a known delay flag, sums flags, then calculates delay share.
- Records only total processing time.
- **Why we changed it:** It cannot compare congestion on *specific dates* and does not separate reading time from computation or measure memory.

## Version 2: Correct hourly congestion and better measurement
- Adds flight date to the grouping: `FL_DATE`, `ORIGIN`, `HOUR`.
- Counts all **scheduled** flights, including cancellations, for congestion; uses only valid non-cancelled departures for the delay-rate denominator.
- Adds congestion bands, delay-share correlation, smaller data types, separate read/compute/combination timings and memory measurement.
- **Why we changed it:** The large set of daily airport-hour rows accumulates as months are added, and the file list is limited to 2023–2025.

## Version 3: My proposed improved baseline (still in development)
- Keeps V2's date-level congestion definition but reduces each month to mergeable summary tables rather than retaining all daily rows across years.
- Uses integer counts/minute totals and computes ratios only after combining months.
- Adds airline, weekday, taxi-out and reported delay-cause analysis; calculates correlation from six additive statistics.
- **My next planned change:** expand the dataset period from **2023–2025 (36 months)** to **2015–2025 (132 months)**. The file in this folder intentionally **still defaults to 2023–2025**, so the expansion is not misrepresented as completed. After acquiring/validating all monthly files, test with `--first-year 2015 --last-year 2025 --months 132`.
- **Still needs testing:** correctness on known examples, missing-minute assumptions, memory on the HPC cluster, and reproducible timing runs. V3 remains sequential, not multiprocessing.

## Important comparison rules
- `DEP_DEL15` means **15 minutes or more**, not strictly greater than 15 minutes.
- These versions do different amounts of work. Comparing their raw runtimes does **not** measure parallel speedup. Strong-scaling speedup must compare a parallel implementation against a sequential baseline doing the **same** computation on the **same** dataset.
- All official timings must come from cluster `sbatch` jobs, with at least five repetitions per configuration.
- If a version is run from `history/`, pass `--data-dir` if its default does not match the location of the raw CSVs. Never commit the raw CSV files.
- Acknowledge any AI assistance according to the course syllabus, and ensure team members review/understand the code they commit.
