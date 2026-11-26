#!/bin/bash
# Submit the whole strong-scaling experiment as a CHAIN of Slurm jobs:
#
#   1. jobs/compare_single_worker_job.sh   baseline vs pool with 1 worker
#                                          (1 CPU, 1 GiB, same job)
#   2. jobs/parallel_pool_job.sh  W        for W = 1 2 4 8 16 32
#                                          (W CPUs, W GiB)
#
# - Every job runs on the SAME node (--nodelist), so all configurations
#   see the same hardware.
# - Each job starts only after the previous one has finished
#   (--dependency=afterany), so the configurations never run at the same
#   time and do not compete for the disk or the memory bandwidth.
#   "afterany" means the chain continues even if one job fails (for
#   example, if one configuration runs out of memory).
# - The job IDs are saved in results/submissions/, so the plot script uses
#   exactly the jobs of this experiment and never mixes in old or pilot runs.
#
# Usage (from the repository root, in the cluster terminal):
#     bash jobs/submit_pool_scaling.sh <NODE> [REPETITIONS]
#
# Examples:
#     bash jobs/submit_pool_scaling.sh julia 1    # pilot: 1 repetition
#     bash jobs/submit_pool_scaling.sh julia      # experiment: 5 repetitions
#
# Optional settings (environment variables):
#     WORKERS_LIST="1 2 4 8 16 32"   worker counts to run
#     MEM_PER_WORKER_GB=1            memory per worker (GiB)
#     CPUS_PER_WORKER=1              Slurm CPUs per worker. Slurm counts each
#                                    hardware thread as a CPU (2 per physical
#                                    core), so 1 = one hardware thread per
#                                    worker (two workers can share a core) and
#                                    2 = one full physical core per worker.
#     INCLUDE_SINGLE=1               0 = skip the single-worker comparison

set -euo pipefail

NODE="${1:?Usage: bash jobs/submit_pool_scaling.sh <NODE> [REPETITIONS]}"
REPETITIONS="${2:-5}"
WORKERS_LIST="${WORKERS_LIST:-1 2 4 8 16 32}"
MEM_PER_WORKER_GB="${MEM_PER_WORKER_GB:-1}"
CPUS_PER_WORKER="${CPUS_PER_WORKER:-1}"
INCLUDE_SINGLE="${INCLUDE_SINGLE:-1}"

# Always work from the repository root
cd "$(dirname "$0")/.."

if [[ ! -d data/OSPC_Flight_Data/raw ]]; then
    echo "Error: data/OSPC_Flight_Data/raw not found. See the README (Dataset)."
    exit 1
fi

if [[ -n "$(git status --porcelain --untracked-files=no 2>/dev/null)" ]]; then
    echo "Warning: the repository has uncommitted changes."
    echo "         The results will not match a commit on GitHub exactly."
fi

mkdir -p results/submissions
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG="results/submissions/${STAMP}_${NODE}_r${REPETITIONS}_c${CPUS_PER_WORKER}.csv"
echo "kind,workers,cpus,mem_gb,repetitions,node,job_id,commit,submitted" > "$LOG"
COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"

PREVIOUS=""

submit() {
    # submit <kind> <workers> <cpus> <mem_gb> <script> [script args...]
    local kind="$1" workers="$2" cpus="$3" mem="$4"
    shift 4
    local dependency=()
    if [[ -n "$PREVIOUS" ]]; then
        dependency=(--dependency="afterany:${PREVIOUS}")
    fi
    local job_id
    job_id=$(sbatch --parsable \
        --nodelist="$NODE" \
        --cpus-per-task="$cpus" \
        --mem="${mem}G" \
        "${dependency[@]}" \
        --export=ALL,MEM_PER_WORKER_MIB=$((MEM_PER_WORKER_GB * 1024)),CPUS_PER_WORKER=$CPUS_PER_WORKER \
        "$@")
    job_id="${job_id%%;*}"
    echo "$kind,$workers,$cpus,$mem,$REPETITIONS,$NODE,$job_id,$COMMIT,$(date --iso-8601=seconds)" >> "$LOG"
    printf "  %-14s workers=%-3s cpus=%-3s mem=%3sG  job %s\n" \
        "$kind" "$workers" "$cpus" "$mem" "$job_id"
    PREVIOUS="$job_id"
}

echo "Submitting to node $NODE, $REPETITIONS repetition(s) per configuration,"
echo "$CPUS_PER_WORKER Slurm CPU(s) and $MEM_PER_WORKER_GB GiB per worker:"

if [[ "$INCLUDE_SINGLE" == "1" ]]; then
    submit single_worker 1 "$CPUS_PER_WORKER" "$MEM_PER_WORKER_GB" \
        jobs/compare_single_worker_job.sh "$REPETITIONS"
fi

for workers in $WORKERS_LIST; do
    submit pool "$workers" $((workers * CPUS_PER_WORKER)) $((workers * MEM_PER_WORKER_GB)) \
        jobs/parallel_pool_job.sh "$workers" "$REPETITIONS"
done

echo
echo "Job IDs saved in $LOG"
echo "Check progress with:  squeue --me"
