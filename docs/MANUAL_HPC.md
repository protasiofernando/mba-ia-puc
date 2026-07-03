# Manual de Uso — Pipeline de Análise de Portfólio no HPC FGV

Pipeline de análise de chamados executado no cluster HPC da FGV com o modelo `gemma4:26b-q8` no nó GPU V100 32 GB. Lê o histórico de chamados do Jira, extrai a intenção de cada chamado via LLM, descobre grupos naturais de demanda e gera recomendações de otimização do portfólio.

---

## PRIMEIRA VEZ — Configuração e execução inicial

Execute estas etapas apenas na primeira vez. Nas execuções seguintes, vá direto para **CICLO DE EXECUÇÕES RECORRENTES**.

### 1. Configurar o ambiente no HPC

Conecte ao head node:
```bash
ssh <seu.usuario>@<head-node>
```

Crie a estrutura de diretórios:
```bash
mkdir -p ~/triagem-chamados/{pipeline,hpc,pipeline_data,data}
```

Crie o ambiente virtual Python:
```bash
cd ~/triagem-chamados
python3 -m venv venv
mkdir -p ~/triagem-chamados/tmp
export TMPDIR=~/triagem-chamados/tmp
venv/bin/pip install --upgrade pip --cache-dir ~/triagem-chamados/tmp -q
venv/bin/pip install pandas scikit-learn numpy requests --cache-dir ~/triagem-chamados/tmp
venv/bin/python3 -c "import pandas, sklearn, numpy, requests; print('OK')"
rm -rf ~/triagem-chamados/tmp/http ~/triagem-chamados/tmp/http-v2 ~/triagem-chamados/tmp/selfcheck
```

Instale o Ollama e baixe o modelo (~20 GB, 20-40 min):
```bash
ollama --version || curl -fsSL https://ollama.com/install.sh | sh
export OLLAMA_HOST=127.0.0.1:11434
ollama serve > /tmp/ollama_setup.log 2>&1 &
OLLAMA_PID=$!
sleep 8
ollama pull gemma4:26b-q8
kill "$OLLAMA_PID"
ollama list | grep gemma4
```

### 2. Transferir os scripts do projeto para o HPC

Do seu computador:
```bash
HPC="<seu.usuario>@<head-node>"
PROJETO="<caminho-local-do-projeto>"

scp "${PROJETO}/data_loader.py"            "${HPC}:~/triagem-chamados/"
scp "${PROJETO}/config_portfolio.json"     "${HPC}:~/triagem-chamados/"
scp "${PROJETO}/pipeline/"*.py             "${HPC}:~/triagem-chamados/pipeline/"
scp "${PROJETO}/hpc/submit_pipeline.sub"   "${HPC}:~/triagem-chamados/hpc/"
scp "${PROJETO}/hpc/run_on_gpu.sh"         "${HPC}:~/triagem-chamados/hpc/"
```

### 3. Continuar com o Ciclo de Execução abaixo

---

## CICLO DE EXECUÇÕES RECORRENTES

Siga esta ordem completa a cada nova execução do pipeline.

### Passo 1 — Exportar os CSVs do Jira

Exporte os chamados do Jira conforme descrito em [GUIA_EXTRACAO_JIRA.md](GUIA_EXTRACAO_JIRA.md). Os arquivos devem seguir o padrão de nomenclatura:
```
Extracao_Jira*.csv   (ex: Extracao_Jira_2024.csv, Extracao_Jira_2026.csv, Extracao_Jira_lote_extra.csv)
```

O pipeline detecta automaticamente todos os CSVs cujo nome começa com `Extracao_Jira` na pasta `data/`. Não há necessidade de editar código ao adicionar um novo ano ou período.

### Passo 2 — Transferir os CSVs para o HPC

Do seu computador (transfira todos os CSVs do período desejado):
```bash
HPC="<seu.usuario>@<head-node>"
scp Extracao_Jira*.csv "${HPC}:~/triagem-chamados/data/"
```

Se houver alterações no `config_portfolio.json` (contexto ou categorias), transferir também:
```bash
scp "config_portfolio.json" "${HPC}:~/triagem-chamados/"
```

Se houver atualizações nos scripts do pipeline:
```bash
scp pipeline/*.py "${HPC}:~/triagem-chamados/pipeline/"
scp hpc/submit_pipeline.sub "${HPC}:~/triagem-chamados/hpc/"
scp hpc/run_on_gpu.sh "${HPC}:~/triagem-chamados/hpc/"
```

### Passo 3 — Verificar a GPU

No HPC:
```bash
ssh <no-gpu> "nvidia-smi"
```

A GPU precisa de ~20 GB livres para o `gemma4:26b-q8`. Se estiver ocupada por outro processo, aguarde antes de submeter.

### Passo 4 — Submeter o job

No HPC:
```bash
cd ~/triagem-chamados
qsub hpc/submit_pipeline.sub
# Retorna: XXXXX.<head-node>
```

> **Importante:** usar sempre `qsub`, nunca `bash submit_pipeline.sub`. O `bash` executa no head node sem GPU.

### Passo 5 — Monitorar

```bash
# Verificar se está rodando e em qual nó
qstat -as | grep $USER

# Acompanhar o log em tempo real
tail -f ~/triagem-chamados/pipeline_data/pipeline.log

# Confirmar GPU ativa (deve mostrar Tesla V100)
head -8 ~/triagem-chamados/pipeline_data/pipeline.log

# Progresso do Stage 2 (o mais longo)
cat ~/triagem-chamados/pipeline_data/02_checkpoint.json | \
python3 -c "import json,sys; d=json.load(sys.stdin); t=len(d.get('processed',{})); print(f'{t} tickets processados')"
```

Tempo estimado:

| Stage | Duração |
|-------|---------|
| 1 — Extração | ~30s |
| 2 — Sumarização LLM | ~90–130 min |
| 3 — Clustering (bge-m3 + K-means) | ~15–20 min |
| 4 — Rotulação | ~10 min |
| 5 — Recomendação | ~5 min |
| 6 — Classificação histórica | ~15–20 min |
| **Total** | **~2,5–3,5 horas** (walltime configurado: 12h, mem: 128gb) |

O padrão atual usa `STAGE2_WORKERS=1`, `STAGE6_WORKERS=1` e `OLLAMA_NUM_PARALLEL=1` para manter o `gemma4:26b-q8` estável na V100 32 GB. A execução pode ficar mais lenta que estimativas antigas com 2 workers, mas evita timeouts e pressão de memória na GPU.

Você receberá um e-mail em `<seu.usuario>@fgv.br` quando o job encerrar.

### Passo 6 — Copiar os resultados para o computador local

Do seu computador:
```bash
HPC="<seu.usuario>@<head-node>"
PROJETO="<caminho-local-do-projeto>"

scp "${HPC}:~/triagem-chamados/pipeline_data/04_labels.json" "${PROJETO}\pipeline_data\"
scp "${HPC}:~/triagem-chamados/pipeline_data/05_portfolio_recommendation.json" "${PROJETO}\pipeline_data\"
scp "${HPC}:~/triagem-chamados/pipeline_data/06_classificados.json" "${PROJETO}\pipeline_data\"
scp "${HPC}:~/triagem-chamados/pipeline_data/07_portfolio_final.json" "${PROJETO}\pipeline_data\"
scp "${HPC}:~/triagem-chamados/pipeline_data/07_classificados_final.json" "${PROJETO}\pipeline_data\"
scp "${HPC}:~/triagem-chamados/pipeline_data/02_summaries.json" "${PROJETO}\pipeline_data\"
```

> `02_summaries.json` é necessário para rodar `python knowledge_base.py` localmente e ativar as métricas de qualidade de descrição no dashboard (aba Análise IA).
> Se os arquivos `07_*` existirem, o dashboard usa o portfólio curado do Stage 7. Se não existirem, usa o recomendado automático dos Stages 5/6.

**Antes de limpar o HPC, valide que os arquivos chegaram corretamente:**
```powershell
dir "<caminho-local-do-projeto>\pipeline_data\04_labels.json"
dir "<caminho-local-do-projeto>\pipeline_data\05_portfolio_recommendation.json"
dir "<caminho-local-do-projeto>\pipeline_data\06_classificados.json"
dir "<caminho-local-do-projeto>\pipeline_data\07_portfolio_final.json"
dir "<caminho-local-do-projeto>\pipeline_data\07_classificados_final.json"
```

Confirme que a data dos arquivos corresponde à execução atual. **Só avance para o Passo 7 após essa validação — nunca limpe o HPC sem confirmar os arquivos locais.**

### Passo 7 — Limpar o HPC

No HPC:
```bash
# Dados sensíveis — CSVs do Jira
rm -f ~/triagem-chamados/data/Extracao_Jira*.csv

# Arquivos intermediários do pipeline
rm -f ~/triagem-chamados/pipeline_data/01_tickets.json
rm -f ~/triagem-chamados/pipeline_data/02_summaries.json
rm -f ~/triagem-chamados/pipeline_data/03_clusters.json
rm -f ~/triagem-chamados/pipeline_data/02_checkpoint.json

# Resultados copiados (já estão no seu computador)
rm -f ~/triagem-chamados/pipeline_data/04_labels.json
rm -f ~/triagem-chamados/pipeline_data/05_portfolio_recommendation.json
rm -f ~/triagem-chamados/pipeline_data/06_classificados.json
rm -f ~/triagem-chamados/pipeline_data/07_portfolio_final.json
rm -f ~/triagem-chamados/pipeline_data/07_classificados_final.json
rm -f ~/triagem-chamados/pipeline_data/06_checkpoint.json
rm -f ~/triagem-chamados/pipeline_data/07_checkpoint.json

# Logs e output PBS
rm -f ~/triagem-chamados/pipeline_data/pipeline.log
rm -f ~/triagem-chamados/pipeline_data/ollama.log
rm -f ~/triagem-chamados/triagem-portfolio.o*
```

Confirme que o HPC ficou limpo:
```bash
find ~/triagem-chamados -not -path "*/venv/*" -not -path "*/__pycache__/*" -not -name "*.pyc" -type f | sort
```

Esperado: apenas os scripts (`pipeline/*.py`, `hpc/*.sh`, `hpc/*.sub`, `data_loader.py`, `config_portfolio.json`).

### Passo 8 — Atualizar o dashboard local

No seu computador (PowerShell):
```powershell
cd "<caminho-local-do-projeto>"

# 1. Apaga o banco antigo
del knowledge_base.db

# 2. Recria o banco lendo os CSVs do Jira
#    (gera knowledge_base.db com estatísticas de chamados para o dashboard)
python knowledge_base.py

# 3. Inicia o dashboard Flask
python app.py
# Acesse: http://localhost:5000
```

O que cada comando faz:
- **`del knowledge_base.db`** — remove o banco antigo para garantir recriação limpa com o schema atualizado
- **`python knowledge_base.py`** — lê os CSVs do Jira e cria o banco SQLite com todos os chamados, incluindo os novos campos (departamento, resolvido, finalizado) e datas em formato correto para o filtro de mês
- **`python app.py`** — inicia o servidor Flask; o dashboard passa a servir os resultados ativos do pipeline (`07_*` curado quando existir; senão `05/06` automático) e os dados do banco recriado

> O banco só precisa ser recriado (`del` + `python knowledge_base.py`) quando os CSVs do Jira mudaram. Se apenas os JSONs do pipeline mudaram, basta reiniciar o `python app.py`.

---

## O que manter no HPC entre execuções

| Item | Manter? | Observação |
|------|:-------:|-----------|
| `venv/` | ✅ Sempre | Nunca apagar |
| `~/.ollama/models/` | ✅ Sempre | Nunca apagar (~17 GB) |
| `pipeline/*.py` | ✅ | Só retransferir se houver atualização |
| `hpc/submit_pipeline.sub` | ✅ | Só retransferir se houver atualização |
| `hpc/run_on_gpu.sh` | ✅ | Só retransferir se houver atualização |
| `data_loader.py` | ✅ | Só retransferir se houver atualização |
| `config_portfolio.json` | ✅ | Retransferir se editar localmente |
| `data/*.csv` | ❌ | Apagar após cada execução — dados sensíveis |
| `pipeline_data/*.json` | ❌ | Apagar após copiar para local |
| `pipeline_data/*.log` | ❌ | Apagar após cada execução |

---

## Referência de Arquivos no HPC

### Entradas necessárias

| Arquivo | Pasta | O que é |
|---------|-------|---------|
| `submit_pipeline.sub` | `hpc/` | Job PBS — submeter com `qsub` |
| `run_on_gpu.sh` | `hpc/` | Executado no nó GPU via mpirun |
| `llm_client.py` | `pipeline/` | Cliente Ollama com retry e parse JSON |
| `01_extract.py` | `pipeline/` | Stage 1: lê os CSVs, limpa e estrutura |
| `02_summarize.py` | `pipeline/` | Stage 2: extrai intenção de cada ticket via LLM |
| `03_cluster.py` | `pipeline/` | Stage 3: agrupa por similaridade (bge-m3 + K-means) |
| `04_label_clusters.py` | `pipeline/` | Stage 4: rotula os grupos via LLM |
| `05_compare_portfolio.py` | `pipeline/` | Stage 5: compara e gera recomendação |
| `06_classify_portfolio.py` | `pipeline/` | Stage 6: reclassifica chamados históricos nas novas categorias |
| `data_loader.py` | `(raiz)` | Lê e combina os CSVs do Jira |
| `config_portfolio.json` | `(raiz)` | Contexto de infraestrutura + categorias obrigatórias (Stages 2 e 5) |
| `Extracao_Jira*.csv` | `data/` | CSVs exportados do Jira — transferir antes de cada execução |
| `venv/` | `(raiz)` | Ambiente virtual Python |
| `~/.ollama/models/` | home | Modelos LLM (`gemma4:26b-q8`) |

### Saídas geradas

| Arquivo | Pasta | Copiar local? | O que contém |
|---------|-------|:---:|---------|
| `01_tickets.json` | `pipeline_data/` | Não | Tickets limpos (intermediário) |
| `02_checkpoint.json` | `pipeline_data/` | Não | Progresso da sumarização |
| `02_summaries.json` | `pipeline_data/` | **Sim** | Intenções extraídas pelo LLM — necessário para `knowledge_base.py` |
| `03_clusters.json` | `pipeline_data/` | Não | Grupos naturais com métricas |
| `04_labels.json` | `pipeline_data/` | **Sim** | Rótulos dos grupos — usado pelo dashboard (abas Grupos Naturais e Análise IA) |
| `05_portfolio_recommendation.json` | `pipeline_data/` | **Sim** | Recomendação automática do portfólio — fallback quando não há Stage 7 |
| `06_classificados.json` | `pipeline_data/` | **Sim** | Chamados históricos reclassificados automaticamente — fallback do Histórico quando não há Stage 7 |
| `07_portfolio_final.json` | `pipeline_data/` | **Sim** | Portfólio final definido pela curadoria humana (Stage 7) |
| `07_classificados_final.json` | `pipeline_data/` | **Sim** | Chamados históricos reclassificados no portfólio curado |
| `pipeline.log` | `pipeline_data/` | Não | Log completo da execução |
| `ollama.log` | `pipeline_data/` | Não | Log do Ollama |
| `triagem-portfolio.oXXXXX` | `(raiz)` | Não | Output PBS (0 bytes) |

---

## Solução de Problemas

### GPU não detectada / modelo rodando em CPU

**Sintoma:** `offloaded 0/31 layers to GPU` no `ollama.log`.

**Causa 1:** job submetido com `bash` em vez de `qsub`.
```bash
qdel XXXXX
cd ~/triagem-chamados && qsub hpc/submit_pipeline.sub
```

**Causa 2:** `run_on_gpu.sh` não encontrado.
```bash
ls -la ~/triagem-chamados/hpc/run_on_gpu.sh
```

### Diagnostico Ollama/CUDA no V100

Use esta checagem antes de rodar jobs longos com LLM local. O objetivo e provar que o modelo foi carregado na V100, e nao em CPU.

Sinais ruins no `pipeline_data/ollama.log`:
```text
inference compute id=cpu library=cpu
load_backend: loaded CPU backend
offloaded 0/31 layers to GPU
model weights device=CPU
```

Sinais bons no `pipeline_data/ollama.log`:
```text
inference compute ... library=CUDA ... Tesla V100-PCIE-32GB
load_backend: loaded CUDA backend from /usr/local/lib/ollama/cuda_v12/libggml-cuda.so
offloaded 31/31 layers to GPU
model weights device=CUDA0
```

Padrao validado no V100 on-premise:
- Chamar explicitamente `/usr/local/bin/ollama`.
- Deixar o Ollama fazer autodiscovery da GPU.
- Nao forcar `CUDA_VISIBLE_DEVICES=0`.
- Nao forcar `OLLAMA_LLM_LIBRARY=cuda`.
- Usar `LD_LIBRARY_PATH` incluindo `/usr/local/lib/ollama/cuda_v12` e as libs CUDA do sistema.

Ambiente minimo que funcionou:
```bash
export LD_LIBRARY_PATH="/usr/local/lib/ollama:/usr/local/lib/ollama/cuda_v12:/usr/local/cuda/lib64:/usr/local/cuda/targets/x86_64-linux/lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export OLLAMA_HOST=127.0.0.1:11434
export OLLAMA_NUM_PARALLEL=1
/usr/local/bin/ollama serve > ~/triagem-chamados/pipeline_data/ollama.log 2>&1 &
```

Teste minimo no host GPU:
```bash
ssh <no-gpu> "pkill -u $USER -f '[o]llama (serve|runner)' || true"

ssh <no-gpu> '
cd ~/triagem-chamados
rm -f pipeline_data/ollama.autogpu-test.log /tmp/ollama-test-response.json
env -u CUDA_VISIBLE_DEVICES -u OLLAMA_LLM_LIBRARY \
  LD_LIBRARY_PATH=/usr/local/lib/ollama:/usr/local/lib/ollama/cuda_v12:/usr/local/cuda/lib64:/usr/local/cuda/targets/x86_64-linux/lib:/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH \
  OLLAMA_DEBUG=1 \
  OLLAMA_HOST=127.0.0.1:11434 \
  OLLAMA_NUM_PARALLEL=1 \
  nohup /usr/local/bin/ollama serve > pipeline_data/ollama.autogpu-test.log 2>&1 < /dev/null &
sleep 8
curl -s http://localhost:11434/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"gemma4:26b-q8\",\"messages\":[{\"role\":\"user\",\"content\":\"Responda apenas OK\"}],\"stream\":false,\"think\":false,\"options\":{\"num_ctx\":512,\"num_predict\":8}}" \
  >/tmp/ollama-test-response.json
nvidia-smi
grep -iE "inference compute|loaded CUDA|offloaded|device=CUDA|library=CUDA|library=cpu|offloaded 0" \
  pipeline_data/ollama.autogpu-test.log | tail -80
cat /tmp/ollama-test-response.json
'
```

Resultado esperado:
```text
library=CUDA
loaded CUDA backend
offloaded 31/31 layers to GPU
/usr/local/bin/ollama usando cerca de 26 GB no nvidia-smi
```

### GPU ocupada por outro usuário

```bash
ssh <no-gpu> "nvidia-smi"
# Precisa de ~20 GB livres
qdel XXXXX
# Aguardar e re-submeter quando livre
```

### CSVs não encontrados (Stage 1 falha)

**Sintoma:** `FileNotFoundError` no log.
```bash
ls ~/triagem-chamados/data/
# Esperado: Extracao_Jira*.csv (um ou mais arquivos por ano/período)
```

### Stage 2 interrompido pelo walltime

Re-submeter — retoma do checkpoint automaticamente:
```bash
qsub hpc/submit_pipeline.sub
```

### Stage 2 aborta por taxa alta de falhas do LLM

**Sintoma:** `taxa de falhas do LLM muito alta`.

Verifique os primeiros erros e o log do Ollama:
```bash
cd ~/triagem-chamados
python3 - <<'PY'
import json
from collections import Counter
with open("pipeline_data/02_checkpoint.json", encoding="utf-8") as f:
    d = json.load(f)
errs = [v.get("_erro") for v in d.get("processed", {}).values() if "_erro" in v]
for erro, n in Counter(errs).most_common(5):
    print(f"\n--- {n}x ---\n{(erro or '')[:1000]}")
PY

grep -iE "error|failed|panic|cuda|memory|oom|runner|timeout|killed" \
  ~/triagem-chamados/pipeline_data/ollama.log | tail -100
```

Antes de reexecutar, mantenha o padrão conservador e limpe o checkpoint:
```bash
rm -f ~/triagem-chamados/pipeline_data/02_checkpoint.json \
      ~/triagem-chamados/pipeline_data/02_summaries.json
qsub hpc/submit_pipeline.sub
```

### Stage 2 com `Resposta vazia do Ollama`

**Sintoma:** taxa alta de `_erro` no Stage 2 com `Resposta vazia do Ollama`.

**Causa:** o `gemma4:26b-q8` é um modelo de raciocínio e precisa ser chamado pelo endpoint `/api/chat` com `think: false`. Sem `think: false` ele gasta o orçamento de tokens raciocinando e devolve `content` vazio. O `pipeline/llm_client.py` já faz isso por padrão — só verifique se não foi alterado.

**Verificação rápida** (no nó GPU, com Ollama de pé) — a chamada correta devolve `done_reason: stop` e JSON no `content`:
```bash
curl -s localhost:11434/api/chat -d '{"model":"gemma4:26b-q8","messages":[{"role":"user","content":"Responda em JSON: {\"ok\": true}"}],"stream":false,"think":false}' \
  | python3 -c "import json,sys; r=json.load(sys.stdin); print('done_reason:', r.get('done_reason')); print('content:', r['message'].get('content'))"
```

Detalhes em [NOTAS_TECNICAS.md](NOTAS_TECNICAS.md).

### Porta 11434 já em uso

```bash
ssh <no-gpu> "pkill -f 'ollama serve'"
```

### Variáveis de paralelismo

Os padrões ficam definidos em `hpc/run_on_gpu.sh`:

| Variável | Padrão | Uso |
|----------|--------|-----|
| `OLLAMA_NUM_PARALLEL` | `1` | Gerações simultâneas permitidas pelo Ollama |
| `STAGE2_WORKERS` | `1` | Tickets simultâneos na sumarização |
| `STAGE6_WORKERS` | `1` | Tickets simultâneos na classificação histórica |

Para teste controlado, é possível exportar valores maiores antes do `qsub`, mas volte para `1/1/1` se houver timeout ou pressão de memória no `ollama.log`.

---

## Referência dos argumentos PBS

```bash
#!/bin/bash
#PBS -N triagem-portfolio      # Nome do job
#PBS -j oe                     # Combina stdout e stderr num único log
#PBS -m abe                    # E-mail ao abortar, começar e encerrar
#PBS -M <seu.usuario>@fgv.br # E-mail de notificação
#PBS -l walltime=12:00:00      # Tempo máximo — job é morto se estourar
#PBS -q gpu                    # Fila com acesso ao V100

cd ${PBS_O_WORKDIR}
mpirun -np 1 --hostfile /home/nfsmpi/ngpu bash run_on_gpu.sh
```

> Para o V100 on-premise, o roteamento para o nó GPU é feito pelo `mpirun` com `--hostfile /home/nfsmpi/ngpu`. Diretivas como `ngpus=1` ou `select` sem mpirun fazem o job rodar no head node sem GPU.

---

## Referência Rápida — Comandos PBS

| Comando | Descrição |
|---------|-----------|
| `qsub hpc/submit_pipeline.sub` | Submeter o job |
| `qstat -as` | Ver todos os jobs na fila |
| `qstat -as \| grep fernand` | Ver seus jobs |
| `qdel XXXXX` | Cancelar um job pelo ID |
| `ssh <no-gpu> "nvidia-smi"` | Ver uso da GPU |

---

## Infraestrutura de Referência

| Recurso | Especificação |
|---------|---------------|
| Usuário | `<seu.usuario>` |
| Head Node | `<head-node>` |
| Nó GPU | `<no-gpu>` — Tesla V100 PCIE 32 GB |
| Driver CUDA | 580.65.06 — CUDA 13.0 |
| Modelo LLM | `gemma4:26b-q8` ("Gemma 4 26B A4B It", raciocínio) via Ollama — usar `/api/chat` + `think: false` |
| Fila usada | `gpu` — walltime máximo 99h |
| Home (NFS) | Compartilhada entre todos os nós |

### Filas PBS disponíveis

| Fila | Tipo | Mem máx | Walltime máx | Uso |
|------|------|--------:|:------------:|-----|
| `pesquisador` | CPU | 500 GB | 168h (7 dias) | Jobs de CPU |
| `gpu` | GPU | 900 GB | 99h | Pipeline — **usar esta** |
