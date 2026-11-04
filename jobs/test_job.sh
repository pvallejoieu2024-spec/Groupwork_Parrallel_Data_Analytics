#!/bin/bash
#SBATCH --job-name=ospc-test
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=4
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=results/test-%j.out

cd "$HOME/ospc-group-project"
export PATH=/data/software/envs/ospc/bin:$PATH

python scripts/test.py
