#!/bin/bash
#PBS -N cmp_prepare
#PBS -l select=1:ncpus=8:ngpus=1
#PBS -l walltime=24:00:00
#PBS -j oe

set -euo pipefail

PROJETO_DIR="${PROJETO_DIR:-${PBS_O_WORKDIR:-$PWD}}"
PREP_DIR="$PROJETO_DIR/estudo_comparativo/preparacao_insumo"
export PIPELINE_DATA_DIR="$PREP_DIR/pipeline_data"
export PIPELINE_START_STAGE=1
export PIPELINE_END_STAGE=2

cd "$PROJETO_DIR"
source "${VENV:-$HOME/venvs/venv}/bin/activate"
python scripts/validar_filtro_sala_sigilo_v6.py

# O job operacional fornece a inicialização Ollama e checkpoints, mas os
# limites acima impedem qualquer Stage 3-6 e isolam os artefatos da v5.
bash "$PROJETO_DIR/scripts/hpc/job_pipeline.sh"

python scripts/registrar_stage2_comparacao_v6.py \
  --pipeline-data "$PIPELINE_DATA_DIR" \
  --scope-manifest \
    "$PROJETO_DIR/estudo_comparativo/filtro_sala_sigilo_manifest_v6.json" \
  --project-root "$PROJETO_DIR" \
  --model "${OLLAMA_MODEL:-llama3.3:70b}" \
  --ollama-tags "$PIPELINE_DATA_DIR/_ollama_tags_at_start.json" \
  --out "$PREP_DIR/MANIFESTO_STAGE2_V6.json"

echo "== Stage 1-2 concluido; manifesto agregado pronto =="
