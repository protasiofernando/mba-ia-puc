#!/bin/bash
#PBS -N pipeline_mba
#PBS -l select=1:ncpus=8:ngpus=1
#PBS -l walltime=24:00:00
#PBS -j oe
#
set -euo pipefail

# Job PBS: sobe o Ollama na GPU reservada e roda o pipeline completo do portal
# (Stage 1 -> 2 -> 3 -> 4 -> 5 -> 6). Os stages por chamado
# (2, descoberta/atribuicao do 3, 4 e 6) usam checkpoints em pipeline_data/,
# entao se o job bater o walltime e so reenviar com qsub que ele continua.

# O PBS NAO herda o PATH do login; o ollama fica em /usr/local/bin.
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

PROJETO_DIR="${PROJETO_DIR:-${PBS_O_WORKDIR:-$PWD}}"
VENV="${VENV:-$HOME/venvs/venv}"
PIPELINE_START_STAGE="${PIPELINE_START_STAGE:-1}"
PIPELINE_END_STAGE="${PIPELINE_END_STAGE:-6}"
case "$PIPELINE_START_STAGE:$PIPELINE_END_STAGE" in
  *[!0-9:]*|:*|*:) echo "ERRO: limites de stage devem ser inteiros."; exit 2 ;;
esac
if [ "$PIPELINE_START_STAGE" -lt 1 ] \
  || [ "$PIPELINE_END_STAGE" -gt 6 ] \
  || [ "$PIPELINE_START_STAGE" -gt "$PIPELINE_END_STAGE" ]; then
  echo "ERRO: intervalo de stages invalido: ${PIPELINE_START_STAGE}-${PIPELINE_END_STAGE}"
  exit 2
fi
PIPELINE_DATA_DIR="${PIPELINE_DATA_DIR:-$PROJETO_DIR/pipeline_data}"
export PIPELINE_DATA_DIR
export OLLAMA_MODELS="$HOME/ollama/models"
export OLLAMA_HOST="127.0.0.1:11434"
export OLLAMA_NUM_PARALLEL="${OLLAMA_NUM_PARALLEL:-2}"
export OLLAMA_KEEP_ALIVE=30m
export OLLAMA_FLASH_ATTENTION=1
# Stages 3 e 5 precisam de contexto maior para consolidacao e leitura do catalogo.
# Ainda assim, limitamos para evitar o default enorme do Ollama.
export OLLAMA_CONTEXT_LENGTH="${OLLAMA_CONTEXT_LENGTH:-32768}"
export PIPELINE_LLM_PROVIDER=ollama
export PIPELINE_WORKERS="${PIPELINE_WORKERS:-2}"
export STAGE3_DISCOVERY_BATCH_SIZE="${STAGE3_DISCOVERY_BATCH_SIZE:-200}"
export STAGE3_OUTLIER_MAX_ROUNDS="${STAGE3_OUTLIER_MAX_ROUNDS:-8}"
export STAGE3_OUTLIER_MIN_GROUP_SIZE="${STAGE3_OUTLIER_MIN_GROUP_SIZE:-2}"
export STAGE3_OUTLIER_SUMMARY_BATCH_SIZE="${STAGE3_OUTLIER_SUMMARY_BATCH_SIZE:-200}"
export STAGE3_MERGE_CHAR_BUDGET="${STAGE3_MERGE_CHAR_BUDGET:-12000}"
export STAGE3_MERGE_MAX_RECORDS="${STAGE3_MERGE_MAX_RECORDS:-20}"
export STAGE3_PLAN_MAX_TOKENS="${STAGE3_PLAN_MAX_TOKENS:-9000}"
export STAGE3_JSON_MAX_TOKENS="${STAGE3_JSON_MAX_TOKENS:-9000}"
export STAGE3_GLOBAL_CHAR_BUDGET="${STAGE3_GLOBAL_CHAR_BUDGET:-60000}"
export STAGE3_GLOBAL_MAX_RECORDS="${STAGE3_GLOBAL_MAX_RECORDS:-160}"
export STAGE3_JSON_MODEL="${STAGE3_JSON_MODEL:-qwen3:30b-a3b-instruct-2507-q4_K_M}"
export STAGE5_JSON_MODEL="${STAGE5_JSON_MODEL:-$STAGE3_JSON_MODEL}"
export STAGE5_WORKERS="${STAGE5_WORKERS:-$PIPELINE_WORKERS}"
export STAGE5_RECONCILE_PLAN_MAX_TOKENS="${STAGE5_RECONCILE_PLAN_MAX_TOKENS:-10000}"
export STAGE5_RECONCILE_JSON_BLOCK_MAX_TOKENS="${STAGE5_RECONCILE_JSON_BLOCK_MAX_TOKENS:-2000}"
export STAGE3_RANDOM_SEED="${STAGE3_RANDOM_SEED:-42}"
export PYTHONUNBUFFERED=1
MODELO="${OLLAMA_MODEL:-llama3.3:70b}"
export OLLAMA_MODEL="$MODELO"
export OLLAMA_BASE_URL="http://127.0.0.1:11434"

# ---- Telemetria de custo (metrica 7 da comparacao justa) ----
# Mede tokens (via llm_client), tempo por stage (TEMPO_CSV) e uso de GPU (GPU_CSV).
# Sem isto, o custo do metodo 2 nao e medido e a comparacao de custo fica so de um lado.
mkdir -p "$PIPELINE_DATA_DIR"
export OLLAMA_METRICS_FILE="${OLLAMA_METRICS_FILE:-$PIPELINE_DATA_DIR/_metrics_tokens.jsonl}"
: > "$OLLAMA_METRICS_FILE"
TEMPO_CSV="$PIPELINE_DATA_DIR/_metrics_tempo.csv"
echo "stage,inicio_epoch,fim_epoch,segundos" > "$TEMPO_CSV"
GPU_CSV="$PIPELINE_DATA_DIR/_metrics_gpu.csv"

mkdir -p "$PROJETO_DIR/logs"
LOG_FILE="$PROJETO_DIR/logs/triagem_${PBS_JOBID:-manual}.log"
if command -v stdbuf >/dev/null 2>&1; then
  exec > >(stdbuf -oL -eL tee -a "$LOG_FILE") 2>&1
else
  exec > >(tee -a "$LOG_FILE") 2>&1
fi

echo "== no: $(hostname) | jobid: ${PBS_JOBID:-manual} | inicio: $(date) =="
echo "log em: $LOG_FILE"
echo "stages: $PIPELINE_START_STAGE -> $PIPELINE_END_STAGE"
echo "pipeline_data: $PIPELINE_DATA_DIR"
echo "ollama em: $(command -v ollama || echo 'NAO ENCONTRADO')"
nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader

source "$VENV/bin/activate"
cd "$PROJETO_DIR"

run_step() {
  local label="$1"
  shift
  local slug; slug=$(echo "$label" | tr ' A-Z' '_a-z')
  export PIPELINE_STAGE="$slug"   # tag da telemetria de tokens (llm_client)
  local ini; ini=$(date +%s)
  echo "== ${label} :: $(date) =="
  set +e
  "$@"
  local rc=$?
  set -e
  local fim; fim=$(date +%s)
  echo "${slug},${ini},${fim},$((fim-ini))" >> "$TEMPO_CSV"
  if [ "$rc" -ne 0 ]; then
    echo "ERRO: ${label} falhou com codigo ${rc}."
    echo "Verifique o log acima antes de reenviar o job."
    exit "$rc"
  fi
}

should_run_stage() {
  local stage="$1"
  [ "$stage" -ge "$PIPELINE_START_STAGE" ] \
    && [ "$stage" -le "$PIPELINE_END_STAGE" ]
}

run_step "Validacao pre-HPC" python scripts/validar_pre_hpc.py
run_step "Validacao dependencias" python -c "import requests"

# sobe o servidor Ollama em background (na GPU reservada pelo PBS)
ollama serve > "$PROJETO_DIR/ollama_serve.log" 2>&1 &
OLLAMA_PID=$!

# amostrador de GPU em background (telemetria de uso, metrica 7)
( echo "timestamp,gpu_util_pct,mem_used_mib,mem_total_mib"
  while true; do
    nvidia-smi --query-gpu=timestamp,utilization.gpu,memory.used,memory.total \
      --format=csv,noheader,nounits 2>/dev/null | tr -d ' '
    sleep 15
  done ) > "$GPU_CSV" 2>/dev/null &
GPU_SAMPLER_PID=$!
trap 'kill $OLLAMA_PID $GPU_SAMPLER_PID 2>/dev/null' EXIT

# espera o servidor responder (ate ~3 min) e aborta cedo se nao subir
echo "aguardando o Ollama subir..."
PRONTO=0
for i in $(seq 1 90); do
  curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && { PRONTO=1; echo "Ollama pronto."; break; }
  sleep 2
done
if [ "$PRONTO" != "1" ]; then
  echo "ERRO: Ollama nao subiu. Ultimas linhas do log:"
  tail -n 20 "$PROJETO_DIR/ollama_serve.log"
  exit 1
fi

# garante o modelo (idempotente: nao rebaixa se ja existe)
ollama pull "$MODELO"
if [ "$PIPELINE_END_STAGE" -ge 3 ] \
  && [ -n "${STAGE3_JSON_MODEL:-}" ] \
  && [ "$STAGE3_JSON_MODEL" != "$MODELO" ]; then
  ollama pull "$STAGE3_JSON_MODEL"
fi
if [ "$PIPELINE_END_STAGE" -ge 5 ] \
  && [ -n "${STAGE5_JSON_MODEL:-}" ] \
  && [ "$STAGE5_JSON_MODEL" != "$MODELO" ] \
  && [ "$STAGE5_JSON_MODEL" != "$STAGE3_JSON_MODEL" ]; then
  ollama pull "$STAGE5_JSON_MODEL"
fi
ollama list
curl -sf http://127.0.0.1:11434/api/tags \
  > "$PIPELINE_DATA_DIR/_ollama_tags_at_start.json"

# ---- Stages selecionados (permite preparacao isolada e retomadas) ----
if should_run_stage 1; then
  run_step "Stage 1" python scripts/extract.py
fi

if should_run_stage 2; then
  if [ ! -f "$PIPELINE_DATA_DIR/01_tickets.json" ]; then
    echo "ERRO: Stage 2 exige $PIPELINE_DATA_DIR/01_tickets.json"
    exit 2
  fi
  run_step "Stage 2" python scripts/run_stage2_llm.py
fi

if should_run_stage 3; then
  if [ ! -f "$PIPELINE_DATA_DIR/02_summaries.json" ]; then
    echo "ERRO: Stage 3 exige $PIPELINE_DATA_DIR/02_summaries.json"
    exit 2
  fi
  run_step "Stage 3" python scripts/run_stage3_llm.py
fi

if should_run_stage 4; then
  if [ ! -f "$PIPELINE_DATA_DIR/03_clusters.json" ]; then
    echo "ERRO: Stage 4 exige $PIPELINE_DATA_DIR/03_clusters.json"
    exit 2
  fi
  run_step "Stage 4" python scripts/run_stage4_llm.py
fi

if should_run_stage 5; then
  if [ ! -f "$PIPELINE_DATA_DIR/04_labels.json" ]; then
    echo "ERRO: Stage 5 exige $PIPELINE_DATA_DIR/04_labels.json"
    exit 2
  fi
  run_step "Stage 5" python scripts/run_stage5_llm.py
  run_step "Validacao Stage 5" \
    python scripts/validar_portfolio.py --stage5-only
fi

if should_run_stage 6; then
  if [ ! -f "$PIPELINE_DATA_DIR/05_portfolio_recommendation.json" ]; then
    echo "ERRO: Stage 6 exige $PIPELINE_DATA_DIR/05_portfolio_recommendation.json"
    exit 2
  fi
  run_step "Stage 6" python scripts/run_stage6_llm.py
  if [ -f "$PIPELINE_DATA_DIR/06_classificados.json" ]; then
    run_step "Validacao Stage 6" python scripts/validar_portfolio.py
  else
    echo "ERRO: Stage 6 nao gerou 06_classificados.json"
    exit 2
  fi
fi

echo "== FIM :: $(date) =="
