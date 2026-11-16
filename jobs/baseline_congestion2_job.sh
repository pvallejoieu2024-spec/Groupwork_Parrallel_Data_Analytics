#!/bin/bash
#SBATCH --job-name=congestion-baseline2
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=512M
#SBATCH --time=00:15:00
#SBATCH --output=results/congestion-baseline2-%j.out

# --mem=512M: the script reads 3.7 GB of CSV month by month and peaks at
# about 450 MiB. Whether this meets the size requirement (brief, 3.1) is
# still being checked with the professor.

set -euo pipefail

# Use the Python environment provided for the course
export PATH=/data/software/envs/ospc/bin:$PATH

# Restrict numerical libraries to one thread
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1

# Go to the repository root
cd "$HOME/Groupwork_Parrallel_Data_Analytics"

# Run the sequential baseline 5 times (the brief asks for at least 5)
for rep in 1 2 3 4 5; do
    python jobs/baseline_congestion2.py \
        --data-dir data/OSPC_Flight_Data/raw \
        --months 132 --results-dir results/v2 \
        --repetition "$rep"
done
