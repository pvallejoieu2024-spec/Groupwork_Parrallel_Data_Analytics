#!/bin/bash
#SBATCH --job-name=congestion-pool
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=64
#SBATCH --mem=24G
#SBATCH --time=01:30:00
#SBATCH --output=results/congestion-pool-%j.out

# Strong scaling of the process-pool version: 132 months, 1-32 workers,
# 5 repetitions each.
# --cpus-per-task=64: Slurm counts each hardware thread as a CPU, so 64
# CPUs = 32 physical cores, enough for 32 workers on separate cores.
# --mem=24G: each worker holds one month in memory (about 0.5 GB peak),
# so 32 workers need about 16 GB plus margin.

set -euo pipefail

export PATH=/data/software/envs/ospc/bin:$PATH

# One thread per worker: no hidden nested parallelism
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1

cd "$HOME/Groupwork_Parrallel_Data_Analytics"
DATA=data/OSPC_Flight_Data/raw

# 1. Correctness first: the pool must match the baseline on a small input
python tests/check_equivalence.py --data-dir "$DATA" --months 3 --workers 3

# 2. Strong scaling
for workers in 1 2 4 8 16 32; do
    for rep in 1 2 3 4 5; do
        python jobs/parallel_pool.py --data-dir "$DATA" --months 132 \
            --workers "$workers" --repetition "$rep"
    done
done
