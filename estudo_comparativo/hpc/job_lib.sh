#!/bin/bash
# Biblioteca comum dos jobs PBS da comparacao robusta.

set -euo pipefail

export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"
BASE_DIR="${COMPARISON_DIR:-${PBS_O_WORKDIR:-$PWD}}"
VENV="${VENV:-$HOME/venvs/venv}"
export OLLAMA_MODELS="${OLLAMA_MODELS:-$HOME/ollama/models}"
export OLLAMA_HOST="127.0.0.1:11434"
export OLLAMA_URL="http://127.0.0.1:11434"
export OLLAMA_BASE_URL="http://127.0.0.1:11434"
export OLLAMA_KEEP_ALIVE="30m"
export OLLAMA_FLASH_ATTENTION=1
export OLLAMA_CONTEXT_LENGTH="32768"
export OLLAMA_NUM_PARALLEL="2"
export OLLAMA_MAX_LOADED_MODELS="1"
export PIPELINE_LLM_PROVIDER=ollama
export PIPELINE_WORKERS="2"
export STAGE5_WORKERS="2"
export STAGE6_WORKERS="1"
export REFERENCE_WORKERS="2"
export LLM_TIMEOUT="90"
export OLLAMA_TIMEOUT="600"
export FIELD_MATCH_THRESHOLD="0.55"
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS="1"
export MKL_NUM_THREADS="1"
export OPENBLAS_NUM_THREADS="1"
export NUMEXPR_NUM_THREADS="1"
export GPU_REQUIRED_PATTERN="A100"

# Parametros efetivos congelados: nenhum valor herdado do shell muda o
# experimento sem aparecer no codigo/protocolo.
export STAGE3_DISCOVERY_BATCH_SIZE="200"
export STAGE3_MERGE_CHAR_BUDGET="12000"
export STAGE3_MERGE_MAX_RECORDS="20"
export STAGE3_MAX_AUTO_OUTLIER_MISSING_RATIO="0.25"
export STAGE3_OUTLIER_MAX_ROUNDS="8"
export STAGE3_OUTLIER_MIN_GROUP_SIZE="2"
export STAGE3_PLAN_MAX_TOKENS="9000"
export STAGE3_JSON_MAX_TOKENS="9000"
export STAGE3_GLOBAL_CHAR_BUDGET="60000"
export STAGE3_GLOBAL_MAX_RECORDS="160"
export STAGE3_OUTLIER_SUMMARY_BATCH_SIZE="200"
export STAGE5_RECONCILE_PLAN_MAX_TOKENS="10000"
export STAGE5_RECONCILE_JSON_BLOCK_MAX_TOKENS="2000"
export EMBED_WORKERS="2"
export MAX_EMBED_FAIL_RATE="0.02"
export EMBED_RETRIES="5"
export K_MIN="4"
export K_MAX="30"
export FORCE_K="0"
export KMEANS_N_INIT="20"
export KMEANS_MAX_ITER="500"
export SILHOUETTE_SAMPLE="0"

OLLAMA_PID=""
GPU_SAMPLER_PID=""
TEMPO_CSV=""
METRICS_DIR=""

init_job() {
  local label="$1"
  local metrics_dir="$2"
  METRICS_DIR="$metrics_dir"
  mkdir -p "$BASE_DIR/logs" "$metrics_dir"
  local job_id="${PBS_JOBID:-manual}"
  local log_file="$BASE_DIR/logs/${label}_${job_id}.log"
  if command -v stdbuf >/dev/null 2>&1; then
    exec > >(stdbuf -oL -eL tee -a "$log_file") 2>&1
  else
    exec > >(tee -a "$log_file") 2>&1
  fi
  export OLLAMA_METRICS_FILE="$metrics_dir/_metrics_tokens.jsonl"
  touch "$OLLAMA_METRICS_FILE"
  TEMPO_CSV="$metrics_dir/_metrics_tempo.csv"
  if [ ! -f "$TEMPO_CSV" ]; then
    echo "stage,inicio_epoch,fim_epoch,segundos,status,job_id" > "$TEMPO_CSV"
  fi
  export GPU_CSV="$metrics_dir/_metrics_gpu.csv"
  if [ ! -f "$GPU_CSV" ]; then
    echo "epoch,gpu_util_pct,mem_used_mib,mem_total_mib,power_w" > "$GPU_CSV"
  fi
  echo "== $label | no=$(hostname) | job=$job_id | inicio=$(date) =="
  echo "base=$BASE_DIR"
  source "$VENV/bin/activate"
}

cleanup_job() {
  if [ -n "${OLLAMA_PID:-}" ]; then
    kill "$OLLAMA_PID" 2>/dev/null || true
  fi
  if [ -n "${GPU_SAMPLER_PID:-}" ]; then
    kill "$GPU_SAMPLER_PID" 2>/dev/null || true
  fi
}

start_ollama() {
  local serve_log="$1"
  local gpu_name
  gpu_name=$(
    nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -n 1
  )
  if [ -z "$gpu_name" ] || [[ "$gpu_name" != *"$GPU_REQUIRED_PATTERN"* ]]; then
    echo "ERRO: GPU '$gpu_name' nao atende ao padrao '$GPU_REQUIRED_PATTERN'."
    exit 2
  fi
  ollama serve > "$serve_log" 2>&1 &
  OLLAMA_PID=$!
  (
    while true; do
      sample=$(
        nvidia-smi \
          --query-gpu=utilization.gpu,memory.used,memory.total,power.draw \
          --format=csv,noheader,nounits 2>/dev/null | head -n 1
      )
      if [ -n "$sample" ]; then
        echo "$(date +%s),$sample" | sed 's/, /,/g'
      fi
      sleep 15
    done
  ) >> "$GPU_CSV" 2>/dev/null &
  GPU_SAMPLER_PID=$!
  trap cleanup_job EXIT
  echo "aguardando Ollama..."
  local ready=0
  for _ in $(seq 1 90); do
    if curl -sf "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 2
  done
  if [ "$ready" != "1" ]; then
    echo "ERRO: Ollama nao iniciou."
    tail -n 40 "$serve_log" || true
    exit 2
  fi
  nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || true
}

sample_gpu_once() {
  local sample
  sample=$(
    nvidia-smi \
      --query-gpu=utilization.gpu,memory.used,memory.total,power.draw \
      --format=csv,noheader,nounits 2>/dev/null | head -n 1
  )
  if [ -n "$sample" ]; then
    echo "$(date +%s),$sample" | sed 's/, /,/g' >> "$GPU_CSV"
  fi
}

ensure_model() {
  local model="$1"
  ollama pull "$model"
}

record_environment() {
  curl -sf "$OLLAMA_URL/api/tags" \
    -o "$METRICS_DIR/_environment_ollama_tags.json"
  curl -sf "$OLLAMA_URL/api/version" \
    -o "$METRICS_DIR/_environment_ollama_version.json"
  nvidia-smi -q > "$METRICS_DIR/_environment_nvidia.txt" 2>&1 || true
  nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null \
    | head -n 1 > "$METRICS_DIR/_environment_gpu_name.txt"
  nvidia-smi --query-gpu=name,memory.total,driver_version \
    --format=csv,noheader,nounits 2>/dev/null \
    | head -n 1 > "$METRICS_DIR/_environment_gpu_identity.txt"
  lscpu > "$METRICS_DIR/_environment_lscpu.txt" 2>&1
  python --version > "$METRICS_DIR/_environment_python.txt" 2>&1
  python -m pip freeze > "$METRICS_DIR/_environment_pip_freeze.txt" 2>&1
  python -c "import numpy as np; np.show_config()" \
    > "$METRICS_DIR/_environment_numpy_config.txt" 2>&1
  (
    cd "$BASE_DIR"
    sha256sum \
      common/scripts/*.py \
      common/config_portfolio.json \
      common/contexto_catalogo.md \
      portfolio_referencia.json \
      feedback_portfolio.json \
      experimento_config.json \
      decision_rules_v1.json
  ) | sort > "$METRICS_DIR/_environment_code_sha256.txt"
}

run_step() {
  local label="$1"
  shift
  local started finished rc slug
  slug=$(echo "$label" | tr ' A-Z' '_a-z')
  export PIPELINE_STAGE="$slug"
  started=$(date +%s)
  sample_gpu_once
  echo "== $label :: $(date) =="
  set +e
  "$@"
  rc=$?
  set -e
  sample_gpu_once
  finished=$(date +%s)
  echo "$slug,$started,$finished,$((finished-started)),$rc,${PBS_JOBID:-manual}" \
    >> "$TEMPO_CSV"
  if [ "$rc" -ne 0 ]; then
    echo "ERRO: $label terminou com codigo $rc."
    exit "$rc"
  fi
}

run_if_missing() {
  local output="$1"
  shift
  local label="$1"
  shift
  if [ -f "$output" ]; then
    if ! python -m json.tool "$output" >/dev/null 2>&1; then
      echo "ERRO: $output existe, mas nao e JSON valido. Mova o artefato "
      echo "truncado para auditoria e retome o mesmo job."
      exit 2
    fi
    python "$BASE_DIR/common/scripts/validar_artefato_retomada.py" \
      --output "$output"
    echo "== $label: $output ja existe; etapa mantida =="
    return 0
  fi
  run_step "$label" "$@"
  if [ ! -f "$output" ]; then
    echo "ERRO: $label terminou sem gerar $output"
    exit 2
  fi
  python "$BASE_DIR/common/scripts/validar_artefato_retomada.py" \
    --output "$output"
}
