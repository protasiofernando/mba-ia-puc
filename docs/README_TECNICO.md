# Guia tecnico vigente

Para retomar o projeto com baixo custo de contexto, comece por
`docs/00_LEIA_PRIMEIRO_IA.md`. Para navegar toda a documentacao, use
`docs/README.md`.

Para compreender e explicar o fluxo completo do MBA, leia
`docs/FLUXO_COMPLETO_MBA.md`. Este arquivo fica como referência curta de
execução; o documento novo é a narrativa técnica canônica.

## Escopo

Este repositório contém três fases relacionadas, mas diferentes:

1. **formação assistida**: o Método Estatístico gera o candidato automático;
2. **curadoria operacional**: a área congela a decisão no nível do catálogo e
   o Stage 7 projeta os chamados automaticamente;
3. **comparação robusta**: reexecuta os dois métodos sobre Stage 2 e alvo
   congelados para medir aderência, estabilidade e custo.

Nao use jobs ou outputs de um fluxo como substitutos do outro.

## Pipeline operacional

Modelos vigentes no A100:

- `llama3.3:70b`: raciocínio semântico;
- `qwen3:30b-a3b-instruct-2507-q4_K_M`: compilação JSON;
- `bge-m3`: embeddings usados somente onde declarados.

Estágios:

| Stage | Implementação | Saída |
|---:|---|---|
| 1 | Python determinístico | `01_tickets.json` |
| 2 | LLM por chamado | `02_summaries.json` |
| 3 | descoberta hierárquica LLM | `03_clusters.json` |
| 4 | rotulagem LLM | `04_labels.json` |
| 5 | recomendação de portfólio | `05_portfolio_recommendation.json` |
| 6 | classificação por chamado | `06_classificados.json` |
| 7 | decisão humana no catálogo + classificação automática fechada | `formacao_portfolio/decisao_curada/feedback_portfolio.json`, `07_portfolio_final.json`, `07_classificados_final.json` |

O Python calcula contagens, cobertura, IDs e contratos. Saída LLM inválida recebe
retry e, se persistir, vira falha rastreável; não existe fallback silencioso
para o primeiro grupo ou categoria.

### Entradas obrigatórias

- `configuracao/projeto.json`;
- `configuracao/config_portfolio.json`;
- `configuracao/contexto_catalogo.md`, com o catálogo real;
- `data/<slug>__YYYY-MM__YYYY-MM.csv`;
- `.env` apenas no ambiente de execução, nunca no Git.

### Execução

Local:

```powershell
python scripts\validar_pre_hpc.py
```

HPC:

```bash
qsub scripts/hpc/job_pipeline.sh
qstat
tail -F logs/triagem_*.log
```

O job executa validação, Stages 1–6 e validadores intermediários.

### Formação do candidato estatístico

O processo que originou o portfólio adotado é formalizado em
`../formacao_portfolio/README.md`. O runner reproduzível é:

```bash
qsub formacao_portfolio/hpc/job_formar_candidato_estatistico.sh
```

Ele gera somente um candidato e evidências. Nunca altera a decisão humana.

## Curadoria e portfólio adotado

`formacao_portfolio/decisao_curada/feedback_portfolio.json` é a decisão operacional da área. Ele incorpora
responsabilidade, governança, navegação e visibilidade de serviços.

`formacao_portfolio/decisao_curada/portfolio_referencia.json` é o espelho estruturado usado pela comparação
robusta. Não é uma segunda curadoria.

Gates e materialização:

```bash
python scripts/materializar_portfolio_curado.py
qsub scripts/hpc/job_stage7_curadoria.sh
```

O primeiro comando valida que curadoria e espelho analítico coincidem. O job
classifica automaticamente todos os chamados no portfólio fechado; nenhuma
pessoa precisa rotular 1.456 registros.

Sala de Sigilo:

- continua visível;
- é atendida pela Segurança da Informação;
- não é modificada;
- não entra na análise metodológica;
- não recebe campos definidos pela DTI Pesquisa.

## Comparação robusta

Ponto de entrada:

[`../estudo_comparativo/DOSSIE_AUDITORIA.md`](../estudo_comparativo/DOSSIE_AUDITORIA.md)

O experimento separa:

- benchmark descritivo de duas arquiteturas completas;
- ablação justa entre K-means e LLM, com Stages 4–6 comuns e três seeds.

O estudo foi concluído no A100. A validação final passou em 302 checks, sem
falhas; a interpretação está em `RESULTADOS_COMPARACAO.md`.

## Guia: como reproduzir o método

Este guia mostra como executar o método de ponta a ponta a partir do
repositório. Ele reproduz **o processo e a maquinaria de medição** quando o
executor fornece uma base compatível. A base real (com PII) não é publicada e,
por política, nenhum CSV sintético integra o Git. Qualquer pessoa pode gerar
localmente uma base inteiramente artificial com o mesmo schema, usando apenas o
catálogo agregado público; seus números serão próprios dessa base. Os resultados oficiais estão em
`resultados_publicaveis/` e interpretados em `RESULTADOS_COMPARACAO.md`.

### Infraestrutura necessária

- **GPU** classe NVIDIA A100 (ou equivalente com VRAM alta) com **Ollama** local.
- Modelos: `llama3.3:70b` (~40 GB), `qwen3:30b-a3b-instruct-2507-q4_K_M` (~18 GB),
  `bge-m3`.
- Python 3.10+ e `pip install -r requirements.txt`.

Os Estágios que usam LLM (2, 3, 4, 5, 6) exigem essa infra. Sem GPU ainda é
possível: rodar o dashboard, a análise de tempo (metadados) e inspecionar os
resultados agregados congelados em `resultados_publicaveis/`.

**Smoke-test sem A100:** para verificar apenas que a mecânica executa, use uma
amostra pequena e um modelo menor (`export OLLAMA_MODEL=<modelo-menor>`). Os
números não terão valor analítico; servem só para provar a execução.

### Base de entrada

O pipeline lê a pasta apontada por `JIRA_DATA_DIR` (padrão `data/`, local e não
publicado). Gere a base sintética e aponte o carregador para a saída:

```bash
python scripts/gerar_base_sintetica.py --amostra 240
export JIRA_DATA_DIR=data_exemplo
```

A base sintética `data_exemplo/dti-pesquisa__sintetica.csv` substitui os CSVs
reais com o mesmo schema. O gerador usa somente
`pipeline_data/07_portfolio_final.json`; textos, pessoas, datas, durações e
interações são criados artificialmente e não preservam linhas ou distribuições
privadas. A saída permanece ignorada pelo Git.

### Passo 1 — formação do candidato (Método Estatístico: bge-m3 + K-means)

Reproduz o processo que originou o portfólio: extração e interpretação (Estágios
1–2) e depois a descoberta estatística com rotulação, consolidação e classificação.

```bash
qsub formacao_portfolio/hpc/job_formar_candidato_estatistico.sh
```

Saída: um candidato automático e evidências em `formacao_portfolio/`. Este passo
**não** decide o catálogo — a curadoria humana faz isso (ver "Curadoria e
portfólio adotado"). Localmente, sem PBS, executam-se os mesmos scripts de Estágio
que o job encapsula, com `JIRA_DATA_DIR=data_exemplo`.

### Passo 2 — reexecutar os dois métodos e medir

O estudo comparativo é empacotado para uma execução controlada. A sequência exata
(referência + insumos comuns, benchmark das arquiteturas, comparação controlada do
motor em três seeds, avaliação) está em
[`../estudo_comparativo/RUNBOOK_HPC.md`](../estudo_comparativo/RUNBOOK_HPC.md), com
as dependências `afterok` e os gates. Em resumo:

```bash
qsub estudo_comparativo/hpc/job_00_referencia.sh        # referência + insumos comuns
qsub estudo_comparativo/hpc/job_10_m1_legado_llama.sh   # benchmark Método Estatístico
qsub estudo_comparativo/hpc/job_20_m2_nativo.sh         # benchmark Método Agêntico
qsub -v RUN_ID=kmeans_common_seed42 estudo_comparativo/hpc/job_30_ablacao.sh
qsub -v RUN_ID=llm_common_seed42    estudo_comparativo/hpc/job_30_ablacao.sh
#   ... demais seeds (31415, 27182) — ver RUNBOOK
qsub estudo_comparativo/hpc/job_90_avaliacao.sh         # avaliação + métricas + pacotes
```

### O que a reprodução entrega — e o que não entrega

- **Entrega:** o processo completo (formação → dois métodos → métricas) executando
  sobre uma base sintética fornecida localmente, com as mesmas métricas (Macro-F1 por serviço, B-cubed,
  ARI, AMI, taxa de reatribuição, custo) e os mesmos gates pré-registrados.
- **Não entrega:** os **números exatos** do trabalho. Esses vêm da base real
  (1.456 chamados), que não é publicada. Na base sintética local os valores são outros, e
  a aderência ao portfólio curado é **ilustrativa** — o alvo é uma decisão humana
  tomada sobre a base real e não foi curado sobre a sintética. Os resultados
  oficiais permanecem em `resultados_publicaveis/`.

## Dashboard

O painel vigente está em `dashboard/`:

```powershell
python dashboard\app.py
```

Validação sem servidor:

```powershell
python -B -c "import sys; sys.path.insert(0, 'dashboard'); import app; c=app.app.test_client(); print(c.get('/api/projeto').json); print(c.get('/').status_code)"
```

`dashboard/runtime/knowledge_base.db` é local e sensível. Sem ele, rotas que dependem de dados
operacionais podem ficar vazias; artefatos agregados do portfólio continuam
disponíveis.

## O que pode ser versionado

Agregados:

- `04_labels.json`;
- `05_portfolio_recommendation.json`;
- `06_quality_report.json`;
- portfólio final agregado;
- protocolo, regras, configuração e resultados agregados da comparação.

Não versionar:

- CSV real;
- `01`, `02`, `03` e classificações por chamado;
- checkpoints;
- banco;
- `.env`;
- logs;
- ledger;
- tar privado.

## Validação local

```powershell
python -B -m unittest tests.test_comparacao_robusta -v
python -B -c "import ast, pathlib; files=list(pathlib.Path('scripts').glob('*.py'))+[pathlib.Path('dashboard/app.py')]; [ast.parse(p.read_text(encoding='utf-8-sig'), filename=str(p)) for p in files]; print('Python syntax ok')"
python scripts\validar_portfolio.py
```

O Bash dos jobs deve ser validado no Linux:

```bash
bash -n scripts/hpc/job_pipeline.sh estudo_comparativo/hpc/*.sh
```
