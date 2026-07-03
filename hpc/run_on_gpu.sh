#!/bin/bash
# =============================================================
# run_on_gpu.sh — Executado no no GPU via mpirun pelo job PBS
# Chamado por submit_pipeline.sub usando:
#   mpirun -np 1 --hostfile /home/nfsmpi/ngpu bash run_on_gpu.sh
# =============================================================

PROJETO_DIR="$HOME/triagem-chamados"
VENV="$PROJETO_DIR/venv/bin/python3"
LOG="$PROJETO_DIR/pipeline_data/pipeline.log"
OLLAMA_BIN="${OLLAMA_BIN:-/usr/local/bin/ollama}"

export LD_LIBRARY_PATH="/usr/local/lib/ollama:/usr/local/lib/ollama/cuda_v12:/usr/local/cuda/lib64:/usr/local/cuda/targets/x86_64-linux/lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export OLLAMA_MODEL="gemma4:26b-q8"
export OLLAMA_URL="http://localhost:11434"
export OLLAMA_HOST="127.0.0.1:11434"
export JIRA_DATA_DIR="$PROJETO_DIR/data"
export OLLAMA_NUM_PARALLEL="${OLLAMA_NUM_PARALLEL:-1}"
export STAGE2_WORKERS="${STAGE2_WORKERS:-1}"
export STAGE6_WORKERS="${STAGE6_WORKERS:-1}"

set -e

cleanup() {
    if [ -n "${OLLAMA_PID:-}" ]; then
        kill "$OLLAMA_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

echo "" >> "$LOG"
echo "[GPU] No: $(hostname)" >> "$LOG"
echo "[GPU] GPU: $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo 'nao detectada')" >> "$LOG"

if curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
    echo "[GPU] ERRO: porta 11434 ja tem um Ollama respondendo. Encerre o processo anterior antes de submeter este job." >> "$LOG"
    exit 1
fi

# Inicia Ollama com paralelismo conservador para caber o gemma4:26b-q8 na V100 32 GB
echo "[GPU] Iniciando Ollama (num_parallel=$OLLAMA_NUM_PARALLEL, stage2_workers=$STAGE2_WORKERS, stage6_workers=$STAGE6_WORKERS)..." >> "$LOG"
"$OLLAMA_BIN" serve > "$PROJETO_DIR/pipeline_data/ollama.log" 2>&1 &
OLLAMA_PID=$!

# Aguarda Ollama ficar pronto (max 60s)
for i in $(seq 1 30); do
    if curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
        echo "[GPU] Ollama pronto (${i}s)" >> "$LOG"
        break
    fi
    sleep 2
done

# Verifica modelo LLM principal
echo "[GPU] Verificando modelo $OLLAMA_MODEL..." >> "$LOG"
if ! "$OLLAMA_BIN" list | grep -q "$OLLAMA_MODEL"; then
    echo "[GPU] Baixando $OLLAMA_MODEL..." >> "$LOG"
    "$OLLAMA_BIN" pull "$OLLAMA_MODEL" >> "$LOG" 2>&1
fi
echo "[GPU] Modelo LLM pronto." >> "$LOG"

# Verifica modelo de embedding (Stage 3)
echo "[GPU] Verificando modelo de embedding bge-m3..." >> "$LOG"
if ! "$OLLAMA_BIN" list | grep -q "bge-m3"; then
    echo "[GPU] Baixando bge-m3..." >> "$LOG"
    "$OLLAMA_BIN" pull bge-m3 >> "$LOG" 2>&1
fi
echo "[GPU] Modelo bge-m3 pronto." >> "$LOG"

# ── Stage 1 ───────────────────────────────────────────────
echo "" >> "$LOG"
echo "====== STAGE 1: Extracao — $(date) ======" >> "$LOG"
PYTHONUNBUFFERED=1 $VENV "$PROJETO_DIR/pipeline/01_extract.py" >> "$LOG" 2>&1
echo "[Stage 1] Concluido: $(date)" >> "$LOG"

# ── Stage 2 ───────────────────────────────────────────────
echo "" >> "$LOG"
echo "====== STAGE 2: Sumarizacao LLM — $(date) ======" >> "$LOG"
echo "ETA disponivel apos os primeiros 10 tickets." >> "$LOG"
PYTHONUNBUFFERED=1 $VENV "$PROJETO_DIR/pipeline/02_summarize.py" >> "$LOG" 2>&1
echo "[Stage 2] Concluido: $(date)" >> "$LOG"

# ── Stage 3 ───────────────────────────────────────────────
echo "" >> "$LOG"
echo "====== STAGE 3: Clustering — $(date) ======" >> "$LOG"
PYTHONUNBUFFERED=1 $VENV "$PROJETO_DIR/pipeline/03_cluster.py" >> "$LOG" 2>&1
echo "[Stage 3] Concluido: $(date)" >> "$LOG"

# ── Stage 4 ───────────────────────────────────────────────
echo "" >> "$LOG"
echo "====== STAGE 4: Rotulacao — $(date) ======" >> "$LOG"
PYTHONUNBUFFERED=1 $VENV "$PROJETO_DIR/pipeline/04_label_clusters.py" >> "$LOG" 2>&1
echo "[Stage 4] Concluido: $(date)" >> "$LOG"

# ── Stage 5 ───────────────────────────────────────────────
echo "" >> "$LOG"
echo "====== STAGE 5: Portfolio — $(date) ======" >> "$LOG"
PYTHONUNBUFFERED=1 $VENV "$PROJETO_DIR/pipeline/05_compare_portfolio.py" >> "$LOG" 2>&1
echo "[Stage 5] Concluido: $(date)" >> "$LOG"

# Reinicia Ollama antes do Stage 6 para evitar degradacao apos Stage 2 longo
echo "" >> "$LOG"
echo "[GPU] Reiniciando Ollama antes do Stage 6..." >> "$LOG"
kill "$OLLAMA_PID" 2>/dev/null || true
for i in $(seq 1 10); do
    if ! curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
        break
    fi
    sleep 1
done
if curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
    echo "[GPU] ERRO: Ollama anterior nao encerrou corretamente antes do Stage 6." >> "$LOG"
    exit 1
fi
"$OLLAMA_BIN" serve > "$PROJETO_DIR/pipeline_data/ollama_stage6.log" 2>&1 &
OLLAMA_PID=$!
for i in $(seq 1 30); do
    if curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
        echo "[GPU] Ollama pronto para Stage 6 (${i}s)" >> "$LOG"
        break
    fi
    sleep 2
done

# ── Stage 6 ───────────────────────────────────────────────
echo "" >> "$LOG"
echo "====== STAGE 6: Classificacao no Portfolio — $(date) ======" >> "$LOG"
PYTHONUNBUFFERED=1 $VENV "$PROJETO_DIR/pipeline/06_classify_portfolio.py" >> "$LOG" 2>&1
echo "[Stage 6] Concluido: $(date)" >> "$LOG"

# Para Ollama
kill "$OLLAMA_PID" 2>/dev/null || true

echo "" >> "$LOG"
echo "====== PIPELINE CONCLUIDO: $(date) ======" >> "$LOG"
ls -lh "$PROJETO_DIR/pipeline_data/"*.json >> "$LOG" 2>&1
