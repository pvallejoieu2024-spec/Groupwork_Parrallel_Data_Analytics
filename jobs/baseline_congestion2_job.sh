#!/bin/bash
#SBATCH --job-name=congestion-baseline2
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:30:00
#SBATCH --output=results/congestion-baseline2-%j.out

# Memory allocation: 1 GiB per worker.
# The full dataset contains 132 monthly CSV files (2015-2025),
# with a total size of 13.157 GB (12.253 GiB).
# The dataset exceeds the allocated job memory, satisfying
# the memory-based workload size criterion if the job completes.

set -euo pipefail

# Use the Python environment provided for the course
export PATH=/data/software/envs/ospc/bin:$PATH

# Restrict numerical libraries to one thread
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

# Go to the repository root
cd "$SLURM_SUBMIT_DIR"

# Create a separate results directory for each job
RESULTS="results/baseline/${SLURM_JOB_ID}"
mkdir -p "$RESULTS"

# Report experimental conditions
echo "Node: $(hostname)"
echo "Job ID: $SLURM_JOB_ID"
echo "CPUs: $SLURM_CPUS_PER_TASK"
echo "Memory: $SLURM_MEM_PER_NODE MiB"

# Run the sequential baseline 5 times
for rep in 1 2 3 4 5; do
    echo "Repetition: $rep"

    python jobs/baseline_congestion2.py \
        --data-dir data/OSPC_Flight_Data/raw \
        --months 132 \
        --results-dir "$RESULTS" \
        --repetition "$rep"
done
