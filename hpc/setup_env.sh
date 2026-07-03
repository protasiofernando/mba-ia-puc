#!/bin/bash
# =============================================================
# setup_env.sh — Executar UMA UNICA VEZ no head node do HPC
# antes de submeter o job pela primeira vez.
#
# O que faz:
#   1. Cria a estrutura de diretorios do projeto
#   2. Cria o ambiente virtual Python
#   3. Instala as dependencias
#   4. Instala o Ollama (se ainda nao instalado)
#   5. Baixa o modelo gemma4:26b-q8 (pode demorar ~30min dependendo da rede)
#
# Como usar:
#   ssh <seu.usuario>@<head-node>
#   cd ~/triagem-chamados
#   bash hpc/setup_env.sh
# =============================================================

set -e

PROJETO_DIR="$HOME/triagem-chamados"
VENV_DIR="$PROJETO_DIR/venv"
MODELO="${OLLAMA_MODEL:-gemma4:26b-q8}"

echo "=============================================="
echo " Setup: Pipeline de Triagem de Chamados FGV"
echo " Projeto: $PROJETO_DIR"
echo "=============================================="

# ------------------------------------------------------------
# 1. Estrutura de diretorios
# ------------------------------------------------------------
echo ""
echo "[1/5] Criando diretorios..."
mkdir -p "$PROJETO_DIR/pipeline_data"
mkdir -p "$PROJETO_DIR/pipeline"
mkdir -p "$PROJETO_DIR/hpc"
mkdir -p "$PROJETO_DIR/data"
echo "      OK: $PROJETO_DIR"

# ------------------------------------------------------------
# 2. Ambiente virtual Python
# ------------------------------------------------------------
echo ""
echo "[2/5] Criando ambiente virtual Python..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "      OK: venv criado em $VENV_DIR"
else
    echo "      OK: venv ja existe"
fi

# Configura TMPDIR para evitar problemas de espaco em /tmp no HPC
mkdir -p "$PROJETO_DIR/tmp"
export TMPDIR="$PROJETO_DIR/tmp"

# ------------------------------------------------------------
# 3. Dependencias Python
# ------------------------------------------------------------
echo ""
echo "[3/5] Instalando dependencias Python..."
"$VENV_DIR/bin/pip" install --upgrade pip --cache-dir "$PROJETO_DIR/tmp" -q

"$VENV_DIR/bin/pip" install \
    pandas==2.2.3 \
    scikit-learn==1.5.0 \
    numpy==1.26.4 \
    requests==2.32.3 \
    --cache-dir "$PROJETO_DIR/tmp" -q

echo "      OK: pandas, scikit-learn, numpy, requests instalados"

# ------------------------------------------------------------
# 4. Ollama
# ------------------------------------------------------------
echo ""
echo "[4/5] Verificando Ollama..."
if command -v ollama &> /dev/null; then
    echo "      OK: Ollama ja instalado ($(ollama --version 2>/dev/null || echo 'versao desconhecida'))"
else
    echo "      Instalando Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
    echo "      OK: Ollama instalado"
fi

# ------------------------------------------------------------
# 5. Modelo gemma4:26b-q8
# ------------------------------------------------------------
echo ""
echo "[5/5] Baixando modelo $MODELO (~20GB, pode demorar 20-40min)..."
echo "      Iniciando Ollama temporariamente para download..."

export OLLAMA_HOST=127.0.0.1:11434
ollama serve > /tmp/ollama_setup.log 2>&1 &
OLLAMA_PID=$!
sleep 8

if ollama list | grep -q "$MODELO"; then
    echo "      OK: Modelo $MODELO ja disponivel"
else
    echo "      Baixando $MODELO..."
    ollama pull "$MODELO"
    echo "      OK: Modelo $MODELO baixado"
fi

# Modelo de embedding para Stage 3
echo "      Verificando bge-m3 (embedding Stage 3)..."
if ollama list | grep -q "bge-m3"; then
    echo "      OK: bge-m3 ja disponivel"
else
    echo "      Baixando bge-m3 (~570MB)..."
    ollama pull bge-m3
    echo "      OK: bge-m3 baixado"
fi

kill $OLLAMA_PID 2>/dev/null || true

# ------------------------------------------------------------
# Instrucoes finais
# ------------------------------------------------------------
echo ""
echo "=============================================="
echo " Setup concluido!"
echo ""
echo " Proximos passos:"
echo ""
echo " 1. Copie os CSVs do Jira para o HPC:"
echo "    scp Extracao_Jira*.csv <seu.usuario>@<head-node>:~/triagem-chamados/data/"
echo ""
echo " 2. Copie os scripts do projeto:"
echo "    scp -r pipeline/ hpc/ data_loader.py config_portfolio.json <seu.usuario>@<head-node>:~/triagem-chamados/"
echo ""
echo " 3. Submeta o job:"
echo "    cd ~/triagem-chamados"
echo "    qsub hpc/submit_pipeline.sub"
echo ""
echo " 4. Monitore:"
echo "    qstat -as"
echo "    tail -f ~/triagem-chamados/pipeline_data/pipeline.log"
echo "=============================================="
