#!/bin/bash
#SBATCH --job-name=single-worker-comparison
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=01:00:00
#SBATCH --output=results/single-worker-%j.out

# Sequential baseline vs process pool with ONE worker, inside the same job,
# with exactly the same resources (1 CPU, 1 GiB). The difference between
# the two is the overhead of the pool (starting a worker process and
# sending each month's tables back to the main process).
#
# The order alternates between repetitions (baseline first in odd
# repetitions, pool first in even ones), so that neither version always
# benefits from files already in the page cache.
#
# At the end, the result tables of both versions are compared on the full
# dataset (tests/compare_outputs.py).
#
# Submit from the repository root:
#     sbatch jobs/compare_single_worker_job.sh
# or let jobs/submit_pool_scaling.sh submit it.

set -euo pipefail

# Python environment
export PATH=/data/software/envs/ospc/bin:$PATH

# Disable implicit library parallelism
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

# Repository root (submit from the repository root)
cd "$SLURM_SUBMIT_DIR"

DATA="data/OSPC_Flight_Data/raw"
MONTHS=132
REPETITIONS="${1:-5}"

# Check the dataset and the allocation
if [[ ! -d "$DATA" ]]; then
    echo "Error: dataset directory not found: $DATA"
    exit 1
fi
if (( SLURM_CPUS_PER_TASK != 1 )) || (( SLURM_MEM_PER_NODE != 1024 )); then
    echo "Error: this job must run with 1 CPU and 1 GiB of memory."
    exit 1
fi

# Store new benchmark results separately
RESULTS="results/single_worker/${SLURM_JOB_ID}"
mkdir -p "$RESULTS"

source jobs/log_conditions.sh

for ((rep=1; rep<=REPETITIONS; rep++)); do

    echo "Repetition $rep"

    if (( rep % 2 == 1 )); then
        ORDER="baseline pool"
    else
        ORDER="pool baseline"
    fi

    for version in $ORDER; do
        if [[ "$version" == "baseline" ]]; then
            python jobs/baseline_congestion2.py \
                --data-dir "$DATA" --months "$MONTHS" \
                --repetition "$rep" --results-dir "$RESULTS" > /dev/null
            tail -n 1 "$RESULTS/timings.csv"
        else
            python jobs/parallel_pool.py \
                --data-dir "$DATA" --months "$MONTHS" --workers 1 \
                --repetition "$rep" --results-dir "$RESULTS"
        fi
    done

done

# Correctness on the full dataset
python tests/compare_outputs.py "$RESULTS" --months "$MONTHS"
