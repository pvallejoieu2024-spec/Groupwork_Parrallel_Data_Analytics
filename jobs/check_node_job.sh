#!/bin/bash
#SBATCH --job-name=check-node
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=4
#SBATCH --mem=1G
#SBATCH --time=00:05:00
#SBATCH --output=results/check-node-%j.out

# Short job to inspect a node BEFORE the experiments:
#   - CPU topology (sockets, cores per socket, threads per core)
#   - which physical core each of the 4 allocated CPUs belongs to:
#     if two CPUs share the same CORE number, Slurm gave us the two
#     hardware threads of one core instead of two separate cores
#   - memory and current load of the node
#
# Usage (from the repository root):
#     sbatch --nodelist=<NODE> jobs/check_node_job.sh
#     cat results/check-node-<JOB_ID>.out

set -euo pipefail
export PATH=/data/software/envs/ospc/bin:$PATH
cd "$SLURM_SUBMIT_DIR"

source jobs/log_conditions.sh

echo "--- Memory of the node ---"
free -g
echo "--- NUMA layout ---"
numactl --hardware 2>/dev/null || lscpu | grep -i numa
echo "--- Other jobs on this node ---"
squeue --nodelist="$(hostname)" 2>/dev/null || true
