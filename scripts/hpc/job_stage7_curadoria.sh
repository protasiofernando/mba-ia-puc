#!/bin/bash
#PBS -N mba_stage7
#PBS -l select=1:ncpus=8:ngpus=1
#PBS -l walltime=24:00:00
#PBS -j oe

set -euo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"
ROOT="${PROJETO_DIR:-${PBS_O_WORKDIR:-$PWD}}"
VENV="${VENV:-$HOME/venvs/venv}"
export OLLAMA_MODELS="$HOME/ollama/models"
export OLLAMA_HOST="127.0.0.1:11434"
export OLLAMA_BASE_URL="http://127.0.0.1:11434"
export OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.3:70b}"
export PIPELINE_LLM_PROVIDER=ollama
export PIPELINE_WORKERS="${PIPELINE_WORKERS:-2}"
export PIPELINE_STAGE=stage7
export PYTHONUNBUFFERED=1
export OLLAMA_METRICS_FILE="$ROOT/pipeline_data/_metrics_stage7_tokens.jsonl"

mkdir -p "$ROOT/logs" "$ROOT/pipeline_data"
LOG="$ROOT/logs/stage7_${PBS_JOBID:-manual}.log"
exec > >(tee -a "$LOG") 2>&1
source "$VENV/bin/activate"
cd "$ROOT"

# Gate deterministico: a decisao curada e seu espelho analitico devem coincidir.
python scripts/materializar_portfolio_curado.py

ollama serve > "$ROOT/ollama_stage7.log" 2>&1 &
OLLAMA_PID=$!
trap 'kill $OLLAMA_PID 2>/dev/null || true' EXIT
READY=0
for _ in $(seq 1 90); do
  curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && { READY=1; break; }
  sleep 2
done
if [ "$READY" != 1 ]; then
  echo "ERRO: Ollama nao iniciou."
  exit 1
fi
ollama pull "$OLLAMA_MODEL"
python scripts/run_stage7_curadoria.py
python scripts/materializar_portfolio_curado.py \
  --write-operational \
  --classifications pipeline_data/07_classificados_final.json

echo "== Stage 7 curado materializado :: $(date) =="
