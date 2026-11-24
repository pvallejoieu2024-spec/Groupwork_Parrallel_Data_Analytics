#!/bin/bash
#SBATCH --job-name=single-worker-comparison
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=01:00:00
#SBATCH --output=results/single-worker-%j.out

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

# Store new benchmark results separately
RESULTS="results/single_worker/${SLURM_JOB_ID}"
mkdir -p "$RESULTS"

echo "Node: $(hostname)"
echo "Job ID: $SLURM_JOB_ID"
echo "CPUs: $SLURM_CPUS_PER_TASK"
echo "Memory: $SLURM_MEM_PER_NODE MiB"

# Five repetitions under identical resource allocations
for rep in 1 2 3 4 5; do

    echo "Repetition $rep"

    if (( rep % 2 == 1 )); then

        python jobs/baseline_congestion2.py \
            --months 132 \
            --repetition "$rep" \
            --results-dir "$RESULTS"

        python jobs/parallel_pool.py \
            --months 132 \
            --workers 1 \
            --repetition "$rep" \
            --results-dir "$RESULTS"

    else

        python jobs/parallel_pool.py \
            --months 132 \
            --workers 1 \
            --repetition "$rep" \
            --results-dir "$RESULTS"

        python jobs/baseline_congestion2.py \
            --months 132 \
            --repetition "$rep" \
            --results-dir "$RESULTS"

    fi

done