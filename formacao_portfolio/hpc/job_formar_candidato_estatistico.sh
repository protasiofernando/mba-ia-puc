#!/bin/bash
#PBS -N mba_forma_km
#PBS -l select=1:ncpus=8:ngpus=1
#PBS -l walltime=24:00:00
#PBS -j oe

set -euo pipefail

# Forma um CANDIDATO automatico pelo Metodo Estatistico. Este job nao escreve
# feedback_portfolio.json e nao define o alvo da comparacao. A decisao humana
# acontece depois, fora do job.

export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"
ROOT="${PROJETO_DIR:-${PBS_O_WORKDIR:-$PWD}}"
VENV="${VENV:-$HOME/venvs/venv}"
SOURCE_STAGE2="${SOURCE_STAGE2:-$ROOT/pipeline_data/02_summaries.json}"
WORK="${FORMACAO_WORKDIR:-$ROOT/formacao_portfolio/execucao}"
PD="$WORK/pipeline_data"
LOG_DIR="$ROOT/formacao_portfolio/logs"
mkdir -p "$WORK/pipeline" "$PD" "$LOG_DIR"

LOG="$LOG_DIR/formacao_${PBS_JOBID:-manual}.log"
exec > >(tee -a "$LOG") 2>&1

source "$VENV/bin/activate"
cd "$ROOT"
python scripts/validar_insumo_formacao.py --input "$SOURCE_STAGE2"

# Snapshot executavel da implementacao estatistica mantida. Um hash composto
# impede retomar checkpoints com codigo diferente.
CODE_SHA="$({
  sha256sum metodo_estatistico/pipeline/*.py
  sha256sum metodo_estatistico/config_portfolio.json
  sha256sum configuracao/contexto_catalogo.md
  sha256sum configuracao/projeto.json
} | sha256sum | awk '{print $1}')"
if [ -f "$WORK/CODE_SHA256" ] && [ "$(cat "$WORK/CODE_SHA256")" != "$CODE_SHA" ]; then
  echo "ERRO: codigo mudou desde o inicio desta execucao; use outro FORMACAO_WORKDIR."
  exit 2
fi
printf '%s\n' "$CODE_SHA" > "$WORK/CODE_SHA256"
cp metodo_estatistico/pipeline/*.py "$WORK/pipeline/"
cp metodo_estatistico/config_portfolio.json "$WORK/config_portfolio.json"
cp configuracao/contexto_catalogo.md "$WORK/contexto_catalogo.md"
cp configuracao/projeto.json "$WORK/projeto.json"
cp metodo_estatistico/requirements.txt "$WORK/requirements.txt"

SOURCE_SHA="$(sha256sum "$SOURCE_STAGE2" | awk '{print $1}')"
if [ -f "$WORK/STAGE2_SHA256" ] && [ "$(cat "$WORK/STAGE2_SHA256")" != "$SOURCE_SHA" ]; then
  echo "ERRO: Stage 2 mudou desde o inicio desta execucao; use outro FORMACAO_WORKDIR."
  exit 2
fi
printf '%s\n' "$SOURCE_SHA" > "$WORK/STAGE2_SHA256"
if [ ! -f "$PD/02_summaries.json" ]; then
  cp "$SOURCE_STAGE2" "$PD/02_summaries.json"
fi

export OLLAMA_MODELS="$HOME/ollama/models"
export OLLAMA_HOST="127.0.0.1:11434"
export OLLAMA_URL="http://127.0.0.1:11434"
export OLLAMA_BASE_URL="http://127.0.0.1:11434"
export OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.3:70b}"
export EMBED_MODEL="${EMBED_MODEL:-bge-m3}"
export PIPELINE_LLM_PROVIDER=ollama
export PIPELINE_WORKERS="${PIPELINE_WORKERS:-2}"
export STAGE6_WORKERS="${STAGE6_WORKERS:-2}"
export PYTHONUNBUFFERED=1
export OLLAMA_METRICS_FILE="$PD/_metrics_tokens.jsonl"

ollama serve > "$WORK/ollama_serve.log" 2>&1 &
OLLAMA_PID=$!
( echo "timestamp,gpu_util_pct,mem_used_mib,mem_total_mib"
  while true; do
    nvidia-smi --query-gpu=timestamp,utilization.gpu,memory.used,memory.total \
      --format=csv,noheader,nounits 2>/dev/null | tr -d ' '
    sleep 15
  done ) > "$PD/_metrics_gpu.csv" 2>/dev/null &
GPU_PID=$!
trap 'kill $OLLAMA_PID $GPU_PID 2>/dev/null || true' EXIT

READY=0
for _ in $(seq 1 90); do
  curl -sf "$OLLAMA_URL/api/tags" >/dev/null 2>&1 && { READY=1; break; }
  sleep 2
done
if [ "$READY" != 1 ]; then
  echo "ERRO: Ollama nao iniciou."
  exit 1
fi
ollama pull "$OLLAMA_MODEL"
ollama pull "$EMBED_MODEL"

TIME_CSV="$PD/_metrics_tempo.csv"
if [ ! -f "$TIME_CSV" ]; then
  echo "stage,inicio_epoch,fim_epoch,segundos" > "$TIME_CSV"
fi
run_stage() {
  local number="$1" script="$2" output="$3"
  if [ -f "$PD/$output" ]; then
    echo "== Stage $number preservado: $output =="
    return
  fi
  export PIPELINE_STAGE="stage${number}"
  local start end rc
  start=$(date +%s)
  set +e
  python "$script"
  rc=$?
  set -e
  end=$(date +%s)
  echo "stage${number},${start},${end},$((end-start))" >> "$TIME_CSV"
  [ "$rc" -eq 0 ] || exit "$rc"
  [ -f "$PD/$output" ] || { echo "ERRO: Stage $number nao gerou $output"; exit 2; }
}

cd "$WORK"
run_stage 3 pipeline/03_cluster.py 03_clusters.json
run_stage 4 pipeline/04_label_clusters.py 04_labels.json
run_stage 5 pipeline/05_compare_portfolio.py 05_portfolio_recommendation.json
run_stage 6 pipeline/06_classify_portfolio.py 06_classificados.json

echo "CANDIDATO_AUTOMATICO=$PD/05_portfolio_recommendation.json"
echo "VALIDACAO_AUTOMATICA=$PD/06_classificados.json"
echo "PROXIMO_PASSO=curadoria humana em formacao_portfolio/decisao_curada/feedback_portfolio.json; este job nao decide o portfolio final"
