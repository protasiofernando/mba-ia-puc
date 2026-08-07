#!/bin/bash
#PBS -N cmp_ref
#PBS -l select=1:ncpus=8:ngpus=1
#PBS -l walltime=24:00:00
#PBS -j oe

set -euo pipefail
source "${PBS_O_WORKDIR:-$PWD}/hpc/job_lib.sh"

MODEL_A="llama3.3:70b"
MODEL_B="qwen3:30b-a3b-instruct-2507-q4_K_M"
EMBED_MODEL="bge-m3"
init_job "referencia" "$BASE_DIR/referencia"
cd "$BASE_DIR"

if [ ! -f source/02_summaries.json ]; then
  echo "ERRO: copie o 02 congelado para $BASE_DIR/source/02_summaries.json"
  exit 2
fi

python common/scripts/validar_insumo_comparacao.py --base "$BASE_DIR"

run_step "deterministic_scope" \
  python common/scripts/preparar_escopo_deterministico_v6.py \
    --summaries "$BASE_DIR/source/02_summaries.json" \
    --filter-manifest \
      "$BASE_DIR/filtro_sala_sigilo_manifest_v6.json" \
    --out-dir "$BASE_DIR/referencia"

start_ollama "$BASE_DIR/referencia/ollama_serve.log"
ensure_model "$MODEL_A"
ensure_model "$MODEL_B"
ensure_model "$EMBED_MODEL"
record_environment
cp "$BASE_DIR/referencia/_environment_pip_freeze.txt" \
  "$BASE_DIR/requirements_frozen_hpc.txt"
cp "$BASE_DIR/referencia/_environment_numpy_config.txt" \
  "$BASE_DIR/NUMPY_BLAS_CONFIG_HPC.txt"
run_step "freeze_environment" \
  python common/scripts/validar_ambiente_comparacao.py \
    --base "$BASE_DIR" --metrics-dir "$BASE_DIR/referencia" \
    --run-id reference --mode freeze

run_step "reference_consensus" \
  python common/scripts/classificar_referencia_consenso.py \
    --summaries "$BASE_DIR/source/02_summaries.json" \
    --portfolio "$BASE_DIR/portfolio_referencia.json" \
    --out-dir "$BASE_DIR/referencia" \
    --scope-mask "$BASE_DIR/referencia/01_scope_mask.json" \
    --model-a "$MODEL_A" \
    --model-b "$MODEL_B" \
    --workers 2

run_step "prepare_common_inputs" \
  python common/scripts/preparar_execucoes_comparacao.py --base "$BASE_DIR"

run_step "validate_setup" \
  python common/scripts/validar_comparacao_robusta.py \
    --base "$BASE_DIR" --phase setup

echo "== referencia e insumos comuns prontos :: $(date) =="
