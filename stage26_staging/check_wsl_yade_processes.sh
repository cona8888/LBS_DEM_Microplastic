#!/usr/bin/env bash
set -u
ps -eo pid,ppid,etimes,stat,pcpu,pmem,args | grep -E '[/]usr/bin/yade|run_stage26q|run_12mm_elastic_rve' || true
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader 2>/dev/null || true
