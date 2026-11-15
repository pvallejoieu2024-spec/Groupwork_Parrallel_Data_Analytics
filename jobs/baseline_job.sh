#!/bin/bash
#SBATCH --job-name=baseline
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:15:00
#SBATCH --output=results/%x-%j.out

export PATH=/data/software/envs/ospc/bin:$PATH
export OMP_NUM_THREADS=1
python jobs/baseline.py --months 36
