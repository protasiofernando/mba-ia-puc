#!/bin/bash
#PBS -N cmp_evaluate
#PBS -l select=1:ncpus=8:ngpus=1
#PBS -l walltime=08:00:00
#PBS -j oe

set -euo pipefail
source "${PBS_O_WORKDIR:-$PWD}/hpc/job_lib.sh"

init_job "avaliacao" "$BASE_DIR/avaliacao"
cd "$BASE_DIR"
start_ollama "$BASE_DIR/avaliacao/ollama_serve.log"
ensure_model "bge-m3"
ensure_model "llama3.3:70b"
ensure_model "qwen3:30b-a3b-instruct-2507-q4_K_M"
record_environment
run_step "verify_environment" \
  python common/scripts/validar_ambiente_comparacao.py \
    --base "$BASE_DIR" --metrics-dir "$BASE_DIR/avaliacao" \
    --run-id avaliacao --mode verify

run_step "validate_results" \
  python common/scripts/validar_comparacao_robusta.py \
    --base "$BASE_DIR" --phase results

run_step "audit_form_fields" \
  python common/scripts/auditar_campos_portfolio.py \
    --summaries "$BASE_DIR/referencia/02_summaries_escopo.json" \
    --reference "$BASE_DIR/referencia/06_referencia_consenso.json" \
    --portfolio "$BASE_DIR/portfolio_referencia.json" \
    --model "bge-m3" \
    --threshold 0.55 \
    --environment-lock "$BASE_DIR/AMBIENTE_CONGELADO.json" \
    --out-dir "$BASE_DIR/avaliacao"

run_step "evaluate_methods" \
  python common/scripts/avaliar_comparacao_robusta.py \
    --base "$BASE_DIR"

run_step "validate_final_report" \
  python common/scripts/validar_comparacao_robusta.py \
    --base "$BASE_DIR" --phase results --require-final-report

mkdir -p "$BASE_DIR/resultados"
STAMP=$(date +%Y%m%d_%H%M%S)
PUBLIC="$BASE_DIR/resultados/comparacao_publicavel_${STAMP}.tar.gz"
PRIVATE="$BASE_DIR/resultados/comparacao_privada_${STAMP}.tar.gz"

tar -czf "$PUBLIC" \
  MANIFESTO_PACOTE.json AMBIENTE_CONGELADO.json \
  requirements_comparacao.txt requirements_frozen_hpc.txt \
  NUMPY_BLAS_CONFIG_HPC.txt \
  experimento_config.json decision_rules_v1.json portfolio_referencia.json \
  feedback_portfolio.json \
  README.md DOSSIE_AUDITORIA.md RUNBOOK_HPC.md PROTOCOLO_METODOLOGICO.md \
  manifesto_insumo_comum.json referencia/06_referencia_quality.json \
  avaliacao/RESULTADO_COMPARACAO_ROBUSTA.md \
  avaliacao/RESULTADO_COMPARACAO_ROBUSTA.metrics.json \
  avaliacao/RESULTADO_CAMPOS_PORTFOLIO.md \
  avaliacao/RESULTADO_CAMPOS_PORTFOLIO.metrics.json \
  avaliacao/VALIDACAO_SETUP.json \
  avaliacao/VALIDACAO_RESULTS.json

tar -czf "$PRIVATE" \
  source/02_summaries.json referencia manifesto_insumo_comum.json \
  metodo1_legado_llama/pipeline_data runs avaliacao

echo "PUBLICAVEL=$PUBLIC"
echo "PRIVADO_NAO_VERSIONAR=$PRIVATE"
echo "== avaliacao concluida :: $(date) =="
