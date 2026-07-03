# Notas Técnicas — Decisões e Inconsistências Conhecidas

## Modelos em uso

**LLM principal (Stages 2, 4, 5):** `gemma4:26b-q8` rodando no nó GPU V100 32 GB.
- Ocupa ~26–28 GB de VRAM dos 32 GB disponíveis
- Definido em `hpc/run_on_gpu.sh` via `OLLAMA_MODEL`

### Como o projeto chama o Ollama (válido para qualquer modelo)

Toda chamada ao LLM passa por `pipeline/llm_client.py` (e, na simulação, por `app.py`). Duas práticas são adotadas e valem para **qualquer modelo Ollama**, não só o atual — são importantes ao trocar de modelo:

**1. Usar o endpoint `/api/chat` (com `messages`), não `/api/generate`.**
O `/api/chat` aplica o template de conversa do modelo; a resposta vem em `message.content`. O `/api/generate` envia o prompt conforme o `TEMPLATE` do Modelfile, que em modelos importados manualmente pode estar incompleto. O `gemma4:26b-q8`, por exemplo, tem `TEMPLATE {{ .Prompt }}` (sem a estrutura de turnos) e só responde corretamente via `/api/chat`.

**2. Enviar `think: false` para desligar o modo de raciocínio.**
Modelos de raciocínio (o `gemma4:26b-q8` é o "Gemma 4 26B A4B It", com chain-of-thought) colocam o raciocínio em `message.thinking` e só depois a resposta em `message.content`. Em prompts grandes eles podem **gastar todo o `num_predict` pensando** e devolver `content` vazio (`done_reason: length`). Como aqui só queremos JSON estruturado, enviamos `think: false`. Em modelos sem raciocínio o parâmetro é ignorado, então é seguro mantê-lo sempre.

Diagnóstico rápido — a chamada correta devolve `done_reason: stop` e JSON em `content`:
```bash
curl -s localhost:11434/api/chat \
  -d '{"model":"gemma4:26b-q8","messages":[{"role":"user","content":"Responda em JSON: {\"ok\":true}"}],"stream":false,"think":false}'
```

**Embedding (Stage 3):** `bge-m3` — modelo multilíngue de embeddings semânticos.
- ~570 MB, carregado junto com o LLM principal sem risco de VRAM
- Usado para agrupar os resumos gerados pelo LLM no Stage 2 por similaridade semântica
- Keywords de cada grupo extraídas dos campos `tema` do Stage 2 (frases LLM, sem TF-IDF)
- Baixado automaticamente pelo `run_on_gpu.sh` se não estiver disponível

## Arquitetura correta para jobs GPU no V100 on-premise

Conforme documentação oficial do HPC FGV, o formato correto para jobs no V100 é:

```bash
#PBS -q gpu
#PBS -l walltime=4:00:00
cd ${PBS_O_WORKDIR}
mpirun -np 1 --hostfile /home/nfsmpi/ngpu bash run_on_gpu.sh
```

- **Sem `ngpus=1`** — não é necessário nem recomendado para o V100 on-premise
- **Sem `select`** — usado apenas para Azure (A100/T4)
- **`mpirun` com `--hostfile /home/nfsmpi/ngpu`** — é o mecanismo oficial que roteia para o nó GPU
- O `submit_pipeline.sub` roda no head node como dispatcher; o `run_on_gpu.sh` executa no nó GPU

Abordagens que **não funcionam** para o V100:
- `bash submit_pipeline.sub` direto — roda no head node sem GPU
- `#PBS -l ngpus=1` sem mpirun — PBS ignora o recurso e aloca qualquer nó

## Ollama/CUDA no V100

O Ollama 0.23.3 no V100 detectou corretamente a GPU quando deixado em autodiscovery. A configuracao validada foi:

```bash
OLLAMA_BIN=/usr/local/bin/ollama
LD_LIBRARY_PATH=/usr/local/lib/ollama:/usr/local/lib/ollama/cuda_v12:/usr/local/cuda/lib64:/usr/local/cuda/targets/x86_64-linux/lib:/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH
OLLAMA_HOST=127.0.0.1:11434
OLLAMA_NUM_PARALLEL=1
```

Nao definir `CUDA_VISIBLE_DEVICES=0` nem `OLLAMA_LLM_LIBRARY=cuda` por padrao. Em teste real, esses overrides fizeram o Ollama cair para CPU, mesmo com `/dev/nvidia0` disponivel e com `libggml-cuda.so` instalada. Sem esses overrides, o log mostrou:

```text
inference compute ... library=CUDA ... Tesla V100-PCIE-32GB
load_backend: loaded CUDA backend from /usr/local/lib/ollama/cuda_v12/libggml-cuda.so
offloaded 31/31 layers to GPU
model weights device=CUDA0
```

O `nvidia-smi` deve mostrar `/usr/local/bin/ollama` consumindo cerca de 26 GB de VRAM para o `gemma4:26b-q8`. Se aparecer `library=cpu`, `loaded CPU backend` ou `offloaded 0/31 layers to GPU`, o job esta rodando em CPU e deve ser cancelado antes de consumir walltime.

## Acesso HPC

| Recurso | Valor |
|---------|-------|
| Usuário no cluster | seu usuário FGV (formato `nome.sobrenome`) |
| E-mail (notificações PBS) | `<seu.usuario>@fgv.br` — editar em `hpc/submit_pipeline.sub` |
| Head node | `<head-node>` |
| Nó GPU | Tesla V100 PCIe 32 GB (alocado via fila `gpu`) |

## Design da interface web

O frontend usa o **tema institucional FGV light**. Não reverter para dark theme. Referências de cor:

| Elemento | Cor |
|----------|-----|
| Canvas da página | `#edf2fa` |
| Cards | `#ffffff` |
| Navy (headings, header) | `#003a79` |
| Azul FGV (accent, links, bordas) | `#008bc9` |
| Texto secundário | `#1e3a5f` |
| Texto muted | `#6b82a0` |

Tipografia: **Montserrat** (headings), **Inter** (body), **IBM Plex Mono** (números e KPIs).

## Simulação — modos disponíveis

A aba Simulação tem dois modos: **LLM Local** (gemma4:26b-q8 no nó GPU, via Ollama) e **LLM OpenAI** (gpt-4.1 via Azure OpenAI).

### Modo LLM Local

Requer duas coisas ao mesmo tempo:

1. Ollama rodando no nó GPU.
2. Um túnel SSH aberto no Windows encaminhando `localhost:11434` do PC para `localhost:11434` do nó GPU.

A janela do túnel fica "parada" depois da senha. Isso é esperado: ela precisa continuar aberta para manter a ponte ativa.

**1. Subir o Ollama no nó GPU** (terminal SSH no HPC):
```bash
cd ~/triagem-chamados
export OLLAMA_HOST=127.0.0.1:11434
export OLLAMA_NUM_PARALLEL=1
export LD_LIBRARY_PATH=/usr/local/lib/ollama:/usr/local/lib/ollama/cuda_v12:/usr/local/cuda/lib64:/usr/local/cuda/targets/x86_64-linux/lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}

nohup /usr/local/bin/ollama serve > pipeline_data/ollama.simulacao.log 2>&1 &
```

**2. Abrir a ponte/túnel SSH** (janela PowerShell separada no Windows; deixar aberta):
```powershell
ssh -L 11434:localhost:11434 -J <seu.usuario>@<head-node> -N <seu.usuario>@<no-gpu>
```

O desenho fica:

```text
Flask no PC -> http://localhost:11434 -> túnel SSH -> Ollama no nó GPU -> gemma4:26b-q8
```

**3. Testar no Windows:**
```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/ollama-status
```

Resposta esperada:
```text
disponivel modelo        url
---------- ------        ---
True       gemma4:26b-q8 http://localhost:11434
```

**4. Rodar o Flask normalmente:**
```powershell
cd "<caminho-local-do-projeto>"
python app.py
```

O badge "LLM Local" na aba Simulação mostra disponibilidade em tempo real. O nó GPU não é acessível de fora da rede FGV — o túnel SSH é obrigatório quando o Flask roda no PC local.

Teste equivalente dentro do HPC, quando estiver no nó GPU:
```bash
curl -s http://127.0.0.1:11434/api/version
```

### Modo LLM OpenAI

Requer recurso Azure OpenAI configurado. Apenas o título e a descrição do chamado digitado são enviados — nunca dados históricos.

Crie um arquivo `.env` na raiz do projeto (nunca versionar — já está no `.gitignore`):

```
AZURE_OPENAI_API_KEY=sua-chave
AZURE_OPENAI_ENDPOINT=https://seu-recurso.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4.1
AZURE_OPENAI_API_VERSION=2025-01-01-preview
```

O badge "OpenAI" na aba Simulação fica verde quando as variáveis estão configuradas. O modelo usa `response_format: {"type": "json_object"}` para garantir JSON válido sem parsing manual.

## Fonte ativa do portfólio no app

O app usa sempre a fonte mais curada disponível:

1. Se `pipeline_data/07_portfolio_final.json` e `pipeline_data/07_classificados_final.json` existem, o dashboard, a simulação, o histórico e o mapeamento usam o Stage 7.
2. Se os arquivos `07_*` não existem, o app usa a recomendação automática dos Stages 5/6 (`05_portfolio_recommendation.json` e `06_classificados.json`, quando disponível).

Isso evita que textos e categorias do portfólio recomendado automático apareçam depois que a área já definiu a curadoria em `feedback_portfolio.json`.

## Estado do pipeline

O pipeline foi executado com sucesso no HPC (versão com `descricao_insuficiente` no Stage 2, embeddings `bge-m3` no Stage 3, e Stage 7 de curadoria final). Os arquivos `pipeline_data/04_labels.json`, `pipeline_data/05_portfolio_recommendation.json` e, quando copiado localmente, `pipeline_data/07_portfolio_final.json` são outputs agregados dessa execução.

Após copiar `02_summaries.json` do HPC para `pipeline_data/`, executar localmente:
```powershell
python knowledge_base.py
```
Isso popula a coluna `descricao_insuficiente` no SQLite, ativando as métricas de qualidade de descrição no dashboard (aba Análise IA). Sem esse passo, o dashboard cai automaticamente para a contagem bruta de `qtd_interacoes` como proxy.

Os demais arquivos intermediários de `pipeline_data/` (01 a 03) e os arquivos de classificação por chamado (`06_classificados.json`, `07_classificados_final.json`) são gitignored por conterem texto, intenções ou dados individuais dos chamados.
