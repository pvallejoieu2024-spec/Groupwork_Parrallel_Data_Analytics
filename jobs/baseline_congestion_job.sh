#!/bin/bash
#SBATCH --job-name=congestion-baseline
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:15:00
#SBATCH --output=results/congestion-baseline-%j.out

set -euo pipefail

# Use the Python environment provided for the course
export PATH=/data/software/envs/ospc/bin:$PATH

# Restrict numerical libraries to one thread
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1

# Go to the repository root
cd "$HOME/Groupwork_Parrallel_Data_Analytics"

# Run the sequential baseline
python jobs/baseline_congestion.py \
    --data-dir data/OSPC_Flight_Data/raw \
    --months 36