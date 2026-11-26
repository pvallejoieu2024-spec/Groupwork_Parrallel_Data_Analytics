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
# Slurm counts each hardware thread as a CPU (2 per physical core).
# CPUS_PER_WORKER=1: one hardware thread per worker (two workers may share a core)
# CPUS_PER_WORKER=2: one full physical core per worker
CPUS_PER_WORKER="${CPUS_PER_WORKER:-1}"
EXPECTED_CPUS=$((WORKERS * CPUS_PER_WORKER))

if (( SLURM_CPUS_PER_TASK != EXPECTED_CPUS )); then
    echo "Error: incorrect CPU allocation (expected $EXPECTED_CPUS, got $SLURM_CPUS_PER_TASK)."
    exit 1
fi

# 1 GiB per worker by default; jobs/submit_pool_scaling.sh can change it
MEM_PER_WORKER_MIB="${MEM_PER_WORKER_MIB:-1024}"
EXPECTED_MEMORY=$((WORKERS * MEM_PER_WORKER_MIB))

if (( SLURM_MEM_PER_NODE != EXPECTED_MEMORY )); then
    echo "Error: incorrect memory allocation (expected $EXPECTED_MEMORY MiB, got $SLURM_MEM_PER_NODE MiB)."
    exit 1
fi

# Create a separate results directory for each job
RESULTS="results/pool/${SLURM_JOB_ID}"
mkdir -p "$RESULTS"

# Report experimental conditions (node, CPUs, memory, topology, load)
source jobs/log_conditions.sh

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
