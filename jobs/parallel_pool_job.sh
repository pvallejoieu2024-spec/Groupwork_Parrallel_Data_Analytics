#!/bin/bash
#SBATCH --job-name=congestion-pool
#SBATCH --partition=cpu
#SBATCH --time=01:30:00
#SBATCH --output=results/congestion-pool-%j.out

# PROCESS POOL - STRONG SCALING BENCHMARK

# Strong scaling:
# The workload remains constant while the number of workers
# increases, allowing us to measure the performance improvement
# obtained through parallel processing.

# CPU and memory resources are specified at submission time
# by the submit_pool_scaling.sh script.

# Following the professor's feedback, we allocate the same
# amount of memory per worker across all configurations.

# Proposed resource allocation:
#   Workers    CPUs    Total memory
#      1         1         1 GiB
#      2         2         2 GiB
#      4         4         4 GiB
#      8         8         8 GiB
#     16        16        16 GiB
#     32        32        32 GiB

# The one-worker configuration is benchmarked separately
# alongside the sequential baseline in the same Slurm job
# using compare_single_worker_job.sh.

# 1. Bash error handling

set -euo pipefail

# 2. Python environment

export PATH=/data/software/envs/ospc/bin:$PATH

# 3. Restrict internal library parallelism

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

# 4. Repository and dataset paths

# SLURM_SUBMIT_DIR is the directory from which sbatch was
# executed.
#
# Using this variable avoids hardcoding a personal directory
# and improves reproducibility for other group members.
#
# The job must be submitted from the repository root.

cd "$SLURM_SUBMIT_DIR"

# Relative path to the complete dataset.
# The raw CSV files are stored locally and are not tracked
# by GitHub because of their large size.

DATA="data/OSPC_Flight_Data/raw"

# Check that the dataset directory exists before starting
# the benchmark.

if [[ ! -d "$DATA" ]]; then
    echo "Error: dataset directory not found: $DATA"
    exit 1
fi


# ------------------------------------------------------------
# 5. Benchmark configuration
# ------------------------------------------------------------

# The first argument specifies the number of process-pool
# workers.
#
# The argument is mandatory because each Slurm job benchmarks
# a single worker configuration.
#
# Example:
#   sbatch --cpus-per-task=4 --mem=4G \
#       jobs/parallel_pool_job.sh 4

WORKERS="${1:?Please specify the number of workers}"

# The second argument specifies the number of repetitions.
#
# By default, each configuration is executed five times,
# as required by the project brief.
#
# During pilot experiments, this can be reduced to one
# repetition to validate the configuration before running
# the complete benchmark.

REPETITIONS="${2:-5}"

# Full workload: 132 months from 2015 to 2025.
# The workload must remain constant across all strong
# scaling configurations.

MONTHS=132

# Proposed memory allocation per worker, expressed in MiB.
# 1024 MiB = 1 GiB.

MEM_PER_WORKER_MIB=1024

# Validate the input arguments.

if [[ ! "$WORKERS" =~ ^[1-9][0-9]*$ ]]; then
    echo "Error: workers must be a positive integer."
    exit 1
fi

if [[ ! "$REPETITIONS" =~ ^[1-9][0-9]*$ ]]; then
    echo "Error: repetitions must be a positive integer."
    exit 1
fi


# ------------------------------------------------------------
# 6. Validate the allocated CPU resources
# ------------------------------------------------------------

# Each process-pool worker is assigned one Slurm CPU in
# our proposed experimental configuration.
#
# Allocating the same number of CPUs as workers avoids
# giving smaller configurations unnecessary CPU resources.
#
# SLURM_CPUS_PER_TASK contains the number of CPUs allocated
# to the job through --cpus-per-task.
#
# Note: a Slurm CPU may represent a physical core or a
# hardware thread, depending on the cluster configuration.
# The node topology must be checked before final benchmarking.

if (( SLURM_CPUS_PER_TASK != WORKERS )); then
    echo "Error: incorrect CPU allocation."
    echo "Expected CPUs: $WORKERS"
    echo "Allocated CPUs: $SLURM_CPUS_PER_TASK"
    exit 1
fi


# ------------------------------------------------------------
# 7. Validate the allocated memory
# ------------------------------------------------------------

# Following the professor's feedback, the total memory
# allocation increases proportionally with the number
# of workers.
#
# Expected memory = number of workers * memory per worker
#
# Previously, all process-pool configurations received
# 24 GiB, while the sequential baseline received 512 MiB.
#
# This created unequal experimental conditions because
# configurations with more available memory could benefit
# from filesystem page caching.
#
# The new allocation removes this fixed-memory imbalance.
# However, it does not guarantee identical page-cache
# conditions across different worker configurations.
#
# SLURM_MEM_PER_NODE reports the requested memory per node
# in MiB when memory is requested using --mem.
#
# This is a job-level memory allocation, not an individual
# memory limit enforced separately on each worker.

EXPECTED_MEMORY=$((WORKERS * MEM_PER_WORKER_MIB))

if (( SLURM_MEM_PER_NODE != EXPECTED_MEMORY )); then
    echo "Error: incorrect memory allocation."
    echo "Expected memory: $EXPECTED_MEMORY MiB"
    echo "Allocated memory: $SLURM_MEM_PER_NODE MiB"
    exit 1
fi


# ------------------------------------------------------------
# 8. Results directory
# ------------------------------------------------------------

# Create a separate results directory for every Slurm job.
#
# Using the unique Slurm job ID prevents new benchmark
# results from being mixed with previous experiments.
#
# It also allows pilot tests and final benchmark results
# to be stored independently.

RESULTS="results/pool/${SLURM_JOB_ID}"

mkdir -p "$RESULTS"


# ------------------------------------------------------------
# 9. Report experimental conditions
# ------------------------------------------------------------

# Record the resources and configuration used for the
# benchmark in the Slurm output file.
#
# This improves reproducibility and allows us to verify
# that all experiments were executed under the intended
# conditions.
#
# The node is selected by the submission script using
# --nodelist, ensuring that the scaling series runs on
# the same machine.

echo "=================================================="
echo "PROCESS POOL BENCHMARK"
echo "=================================================="
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "Allocated CPUs: $SLURM_CPUS_PER_TASK"
echo "Workers: $WORKERS"
echo "Allocated memory: $SLURM_MEM_PER_NODE MiB"
echo "Memory per worker: $MEM_PER_WORKER_MIB MiB"
echo "Months: $MONTHS"
echo "Repetitions: $REPETITIONS"
echo "Dataset directory: $DATA"
echo "Results directory: $RESULTS"
echo "Start time: $(date)"
echo "=================================================="


# ------------------------------------------------------------
# 10. Execute the process-pool benchmark
# ------------------------------------------------------------

# Run the same workload multiple times for the selected
# number of workers.
#
# Repetitions help reduce the influence of runtime variability
# caused by factors such as:
#   - Other jobs running on the node
#   - Operating system scheduling
#   - Filesystem caching
#   - I/O contention
#
# The recorded execution times will later be used to calculate
# the median runtime, speedup and scaling efficiency.
#
# Speedup must be calculated relative to the sequential
# baseline, not relative to the process pool with one worker.
#
# The one-worker process pool is reported separately to
# evaluate multiprocessing overhead.

for ((rep=1; rep<=REPETITIONS; rep++)); do

    echo ""
    echo "--------------------------------------------------"
    echo "Workers: $WORKERS"
    echo "Repetition: $rep / $REPETITIONS"
    echo "Start time: $(date)"
    echo "--------------------------------------------------"

    python jobs/parallel_pool.py \
        --data-dir "$DATA" \
        --months "$MONTHS" \
        --workers "$WORKERS" \
        --results-dir "$RESULTS" \
        --repetition "$rep"

    echo "Repetition $rep completed successfully."
    echo "End time: $(date)"

done


# ------------------------------------------------------------
# 11. Benchmark completion
# ------------------------------------------------------------

# This message is only reached if all repetitions have
# completed successfully.
#
# Correctness and equivalence tests are executed separately
# before the final benchmarking experiments to avoid
# introducing additional computation and cache effects
# immediately before the timed runs.

echo ""
echo "=================================================="
echo "BENCHMARK COMPLETED SUCCESSFULLY"
echo "=================================================="
echo "Workers: $WORKERS"
echo "Completed repetitions: $REPETITIONS"
echo "Results saved in: $RESULTS"
echo "End time: $(date)"
echo "=================================================="
