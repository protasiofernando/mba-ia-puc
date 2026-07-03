#!/bin/bash
# =============================================================
# run_stage7.sh — Stage 7 (finalizacao/reclassificacao) no no GPU.
#
# Roda DEPOIS dos Stages 1-6 e da curadoria humana (feedback_portfolio.json).
# Le o portfolio final definido pela area e reclassifica os historicos nele.
# Despachado por hpc/stage7.sub via mpirun.
#
# Le:  feedback_portfolio.json, pipeline_data/02_summaries.json
# Grava: pipeline_data/07_portfolio_final.json, pipeline_data/07_classificados_final.json
# =============================================================

PROJETO_DIR="$HOME/triagem-chamados"
VENV="$PROJETO_DIR/venv/bin/python3"
LOG="$PROJETO_DIR/pipeline_data/pipeline.log"
OLLAMA_BIN="${OLLAMA_BIN:-/usr/local/bin/ollama}"

export LD_LIBRARY_PATH="/usr/local/lib/ollama:/usr/local/lib/ollama/cuda_v12:/usr/local/cuda/lib64:/usr/local/cuda/targets/x86_64-linux/lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export OLLAMA_MODEL="gemma4:26b-q8"
export OLLAMA_URL="http://localhost:11434"
export OLLAMA_HOST="127.0.0.1:11434"
export OLLAMA_NUM_PARALLEL="${OLLAMA_NUM_PARALLEL:-1}"
export STAGE7_WORKERS="${STAGE7_WORKERS:-1}"

set -e

cleanup() {
    if [ -n "${OLLAMA_PID:-}" ]; then
        kill "$OLLAMA_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

echo "" >> "$LOG"
echo "====== STAGE 7: Finalizacao (portfolio definido) — $(date) ======" >> "$LOG"
echo "[GPU] No: $(hostname)" >> "$LOG"
echo "[GPU] GPU: $(nvidia-smi --query-gpu=name,memory.free --format=csv,noheader 2>/dev/null || echo 'nao detectada')" >> "$LOG"

if [ ! -f "$PROJETO_DIR/feedback_portfolio.json" ]; then
    echo "[Stage 7] ERRO: feedback_portfolio.json nao encontrado. Faca a curadoria antes." >> "$LOG"
    exit 1
fi

if curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
    echo "[GPU] ERRO: porta 11434 ja tem um Ollama respondendo. Encerre o processo anterior." >> "$LOG"
    exit 1
fi

echo "[GPU] Iniciando Ollama (num_parallel=$OLLAMA_NUM_PARALLEL, stage7_workers=$STAGE7_WORKERS)..." >> "$LOG"
"$OLLAMA_BIN" serve > "$PROJETO_DIR/pipeline_data/ollama.log" 2>&1 &
OLLAMA_PID=$!

for i in $(seq 1 30); do
    if curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
        echo "[GPU] Ollama pronto (${i}x2s)" >> "$LOG"
        break
    fi
    sleep 2
done

echo "[GPU] Verificando modelo $OLLAMA_MODEL..." >> "$LOG"
if ! "$OLLAMA_BIN" list | grep -q "$OLLAMA_MODEL"; then
    echo "[GPU] ERRO: modelo $OLLAMA_MODEL nao encontrado." >> "$LOG"
    exit 1
fi

PYTHONUNBUFFERED=1 $VENV "$PROJETO_DIR/pipeline/07_finalize_portfolio.py" >> "$LOG" 2>&1
echo "[Stage 7] Concluido: $(date)" >> "$LOG"
