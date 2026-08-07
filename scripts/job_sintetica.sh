#!/bin/bash
#PBS -N base_sintetica
#PBS -l select=1:ncpus=1
#PBS -l walltime=00:10:00
#PBS -j oe
#
set -euo pipefail

# Gera uma base demonstrativa totalmente artificial a partir do portfolio
# agregado e publico. Nao usa LLM, GPU, chamados reais ou artefatos privados.
# Saida:
#   GEN_DIR/data_exemplo/dti-pesquisa__sintetica.csv

export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"
GEN_DIR="${GEN_DIR:-$PWD}"
VENV="${VENV:-$HOME/venvs/venv}"
export PYTHONUNBUFFERED=1
AMOSTRA="${AMOSTRA:-300}"

cd "$GEN_DIR"
if [ -f "$VENV/bin/activate" ]; then
  source "$VENV/bin/activate"
fi

echo "== base_sintetica :: $(hostname) :: $(date) =="
echo "GEN_DIR=$GEN_DIR  AMOSTRA=$AMOSTRA"
[ -f pipeline_data/07_portfolio_final.json ] || {
  echo "ERRO: falta pipeline_data/07_portfolio_final.json em $GEN_DIR"; exit 2; }

python scripts/gerar_base_sintetica.py --amostra "$AMOSTRA"

echo "== FIM :: $(date) =="
echo "saida: $GEN_DIR/data_exemplo/dti-pesquisa__sintetica.csv"
echo "Base artificial para demonstracao local; o CSV permanece fora do Git."
