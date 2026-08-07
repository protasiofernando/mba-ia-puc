#!/bin/bash
#PBS -N cmp_m1_leg_llama
#PBS -l select=1:ncpus=8:ngpus=1
#PBS -l walltime=16:00:00
#PBS -j oe

set -euo pipefail
source "${PBS_O_WORKDIR:-$PWD}/hpc/job_lib.sh"

RUN_ID="m1_legacy_llama"
RUN_DIR="$BASE_DIR/metodo1_legado_llama"
PD="$RUN_DIR/pipeline_data"
export OLLAMA_MODEL="llama3.3:70b"
export EMBED_MODEL="bge-m3"
export OLLAMA_URL="http://127.0.0.1:11434"

init_job "$RUN_ID" "$PD"
cd "$BASE_DIR"
run_step "validate_setup" \
  python common/scripts/validar_comparacao_robusta.py \
    --base "$BASE_DIR" --phase setup

start_ollama "$PD/ollama_serve.log"
ensure_model "$OLLAMA_MODEL"
ensure_model "$EMBED_MODEL"
ensure_model "qwen3:30b-a3b-instruct-2507-q4_K_M"
record_environment
run_step "verify_environment" \
  python common/scripts/validar_ambiente_comparacao.py \
    --base "$BASE_DIR" --metrics-dir "$PD" \
    --run-id "$RUN_ID" --mode verify

cd "$RUN_DIR"
run_if_missing "$PD/03_clusters.json" "stage3" \
  python pipeline/03_cluster.py
run_if_missing "$PD/04_labels.json" "stage4" \
  python pipeline/04_label_clusters.py
run_if_missing "$PD/05_portfolio_recommendation.json" "stage5" \
  python pipeline/05_compare_portfolio.py
run_if_missing "$PD/06_classificados.json" "stage6" \
  python pipeline/06_classify_portfolio.py

echo "== arquitetura legada com Llama concluida :: $(date) =="
