#!/bin/bash
# Print the experimental conditions of a Slurm job.
# Sourced by every job script: `source jobs/log_conditions.sh`
# The output goes to the job's .out file, so every result folder can be
# traced back to the node, the CPUs and the memory it ran with.

echo "================ EXPERIMENTAL CONDITIONS ================"
echo "Date:            $(date --iso-8601=seconds)"
echo "Node:            $(hostname)"
echo "Job ID:          ${SLURM_JOB_ID:-none}"
echo "CPUs (Slurm):    ${SLURM_CPUS_PER_TASK:-?}"
echo "Memory (Slurm):  ${SLURM_MEM_PER_NODE:-?} MiB"
echo "CPU IDs allowed: $(grep Cpus_allowed_list /proc/self/status | awk '{print $2}')"
echo "Load (1/5/15m):  $(cut -d' ' -f1-3 /proc/loadavg)"
echo "Git commit:      $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo "Python:          $(python --version 2>&1)"
echo "pandas:          $(python -c 'import pandas; print(pandas.__version__)' 2>/dev/null)"
echo "--- CPU topology (lscpu) ---"
lscpu | grep -E "^(Model name|Socket\(s\)|Core\(s\) per socket|Thread\(s\) per core|CPU\(s\)|NUMA node\(s\))" || true
echo "--- Which core each allowed CPU belongs to (CPU,CORE,SOCKET,NODE) ---"
for cpu in $(python -c "import os; print(' '.join(map(str, sorted(os.sched_getaffinity(0)))))"); do
    lscpu -p=CPU,CORE,SOCKET,NODE | grep -v '^#' | awk -F, -v c="$cpu" '$1==c'
done | head -70
echo "=========================================================="
