#!/bin/bash
#SBATCH --job-name=congestion-pool
#SBATCH --partition=cpu
#SBATCH --time=01:30:00
#SBATCH --output=results/congestion-pool-%j.out

# CPU and memory resources are specified at submission time.
# Each worker is allocated one CPU and 1 GiB of memory.
# The workload remains constant across all configurations.

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

# Configure the process pool
DATA="data/OSPC_Flight_Data/raw"
WORKERS="${1:?Please specify the number of workers}"
REPETITIONS="${2:-5}"
MONTHS=132

# Validate input arguments
if [[ ! "$WORKERS" =~ ^[1-9][0-9]*$ ]]; then
    echo "Error: workers must be a positive integer."
    exit 1
fi

if [[ ! "$REPETITIONS" =~ ^[1-9][0-9]*$ ]]; then
    echo "Error: repetitions must be a positive integer."
    exit 1
fi

# Check that the dataset exists
if [[ ! -d "$DATA" ]]; then
    echo "Error: dataset directory not found: $DATA"
    exit 1
fi

# Validate CPU and memory allocation
if (( SLURM_CPUS_PER_TASK != WORKERS )); then
    echo "Error: incorrect CPU allocation."
    exit 1
fi

EXPECTED_MEMORY=$((WORKERS * 1024))

if (( SLURM_MEM_PER_NODE != EXPECTED_MEMORY )); then
    echo "Error: incorrect memory allocation."
    exit 1
fi

# Create a separate results directory for each job
RESULTS="results/pool/${SLURM_JOB_ID}"
mkdir -p "$RESULTS"

# Report experimental conditions
echo "Node: $(hostname)"
echo "Job ID: $SLURM_JOB_ID"
echo "CPUs: $SLURM_CPUS_PER_TASK"
echo "Memory: $SLURM_MEM_PER_NODE MiB"
echo "Workers: $WORKERS"
echo "Repetitions: $REPETITIONS"

# Run the process pool 5 times by default
for ((rep=1; rep<=REPETITIONS; rep++)); do
    echo "Repetition: $rep"

    python jobs/parallel_pool.py \
        --data-dir "$DATA" \
        --months "$MONTHS" \
        --workers "$WORKERS" \
        --results-dir "$RESULTS" \
        --repetition "$rep"
done
