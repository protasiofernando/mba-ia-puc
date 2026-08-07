#!/bin/bash
#PBS -N cmp_m2_native
#PBS -l select=1:ncpus=8:ngpus=1
#PBS -l walltime=24:00:00
#PBS -j oe

set -euo pipefail
source "${PBS_O_WORKDIR:-$PWD}/hpc/job_lib.sh"

RUN_ID="m2_native"
PD="$BASE_DIR/runs/$RUN_ID/pipeline_data"
export PIPELINE_DATA_DIR="$PD"
export PORTFOLIO_CONFIG_PATH="$BASE_DIR/common/config_portfolio.json"
export CATALOG_CONTEXT_PATH="$BASE_DIR/common/contexto_catalogo.md"
export OLLAMA_MODEL="llama3.3:70b"
export STAGE3_JSON_MODEL="qwen3:30b-a3b-instruct-2507-q4_K_M"
export STAGE5_JSON_MODEL="$STAGE3_JSON_MODEL"
export STAGE3_RANDOM_SEED=42

init_job "$RUN_ID" "$PD"
cd "$BASE_DIR"
run_step "validate_setup" \
  python common/scripts/validar_comparacao_robusta.py \
    --base "$BASE_DIR" --phase setup

start_ollama "$PD/ollama_serve.log"
ensure_model "$OLLAMA_MODEL"
ensure_model "$STAGE3_JSON_MODEL"
ensure_model "bge-m3"
record_environment
run_step "verify_environment" \
  python common/scripts/validar_ambiente_comparacao.py \
    --base "$BASE_DIR" --metrics-dir "$PD" \
    --run-id "$RUN_ID" --mode verify

run_if_missing "$PD/03_clusters.json" "stage3" \
  python common/scripts/run_stage3_llm.py
run_if_missing "$PD/04_labels.json" "stage4" \
  python common/scripts/run_stage4_llm.py
run_if_missing "$PD/05_portfolio_recommendation.json" "stage5" \
  python common/scripts/run_stage5_llm.py
run_step "validate_stage5" \
  python common/scripts/validar_portfolio.py --stage5-only
run_if_missing "$PD/06_classificados.json" "stage6" \
  python common/scripts/run_stage6_llm.py
run_step "validate_stage6" \
  python common/scripts/validar_portfolio.py

echo "== m2 nativo concluido :: $(date) =="
