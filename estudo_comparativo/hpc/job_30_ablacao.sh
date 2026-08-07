#!/bin/bash
#PBS -N cmp_ablation
#PBS -l select=1:ncpus=8:ngpus=1
#PBS -l walltime=24:00:00
#PBS -j oe

set -euo pipefail
source "${PBS_O_WORKDIR:-$PWD}/hpc/job_lib.sh"

RUN_ID="${RUN_ID:-}"
case "$RUN_ID" in
  llm_common_seed42) DISCOVERY="llm"; SEED=42 ;;
  kmeans_common_seed42) DISCOVERY="kmeans"; SEED=42 ;;
  llm_common_seed31415) DISCOVERY="llm"; SEED=31415 ;;
  kmeans_common_seed31415) DISCOVERY="kmeans"; SEED=31415 ;;
  llm_common_seed27182) DISCOVERY="llm"; SEED=27182 ;;
  kmeans_common_seed27182) DISCOVERY="kmeans"; SEED=27182 ;;
  *)
    echo "ERRO: RUN_ID invalido. Use um id *_common_* de experimento_config.json."
    exit 2
    ;;
esac

PD="$BASE_DIR/runs/$RUN_ID/pipeline_data"
export PIPELINE_DATA_DIR="$PD"
export PORTFOLIO_CONFIG_PATH="$BASE_DIR/common/config_portfolio.json"
export CATALOG_CONTEXT_PATH="$BASE_DIR/common/contexto_catalogo.md"
export OLLAMA_MODEL="llama3.3:70b"
export STAGE3_JSON_MODEL="qwen3:30b-a3b-instruct-2507-q4_K_M"
export STAGE5_JSON_MODEL="$STAGE3_JSON_MODEL"
export STAGE3_RANDOM_SEED="$SEED"
export KMEANS_RANDOM_SEED="$SEED"
export EMBED_MODEL="bge-m3"
export EMBED_BATCH_SIZE=32
export EMBED_RETRIES=5
export K_MIN=4
export K_MAX=30
export FORCE_K=0
export KMEANS_N_INIT=20
export KMEANS_MAX_ITER=500
export SILHOUETTE_SAMPLE=0

init_job "$RUN_ID" "$PD"
cd "$BASE_DIR"
run_step "validate_setup" \
  python common/scripts/validar_comparacao_robusta.py \
    --base "$BASE_DIR" --phase setup

start_ollama "$PD/ollama_serve.log"
ensure_model "$OLLAMA_MODEL"
ensure_model "$STAGE3_JSON_MODEL"
ensure_model "$EMBED_MODEL"
if [ "$DISCOVERY" = "kmeans" ]; then
  record_environment
  run_step "verify_environment" \
    python common/scripts/validar_ambiente_comparacao.py \
      --base "$BASE_DIR" --metrics-dir "$PD" \
      --run-id "$RUN_ID" --mode verify
  run_if_missing "$PD/03_clusters.json" "stage3" \
    python common/scripts/run_stage3_kmeans_fair.py
else
  record_environment
  run_step "verify_environment" \
    python common/scripts/validar_ambiente_comparacao.py \
      --base "$BASE_DIR" --metrics-dir "$PD" \
      --run-id "$RUN_ID" --mode verify
  run_if_missing "$PD/03_clusters.json" "stage3" \
    python common/scripts/run_stage3_llm.py
fi

run_step "canonicalize_stage3" \
  python common/scripts/normalizar_stage3_comum.py \
    --pipeline-data "$PD"
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

echo "== ablacao $RUN_ID concluida :: $(date) =="
