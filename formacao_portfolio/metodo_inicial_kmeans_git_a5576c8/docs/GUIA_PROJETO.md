# Guia do Projeto — Triagem Inteligente de Chamados

Para o contexto e os objetivos do projeto, consulte [CONTEXTO_OBJETIVOS.md](CONTEXTO_OBJETIVOS.md).
Para o passo a passo detalhado de execução no HPC, consulte [MANUAL_HPC.md](MANUAL_HPC.md).
Para uma orientação curta para IAs e novos mantenedores, consulte [../AGENTS.md](../AGENTS.md).

---

## Estrutura de pastas e arquivos

```
triagem-chamados-ia/
│
│  ── Aplicação web (dashboard) ──────────────────────────────────────
├── app.py                       # Entry point Flask — inicia o dashboard em localhost:5000
├── category_analyzer.py         # Calcula estatísticas das categorias a partir dos CSVs do Jira
├── data_loader.py               # Lê e combina os CSVs do Jira em um DataFrame único
├── knowledge_base.py            # Cria/popula o banco SQLite — rodar após pipeline; inclui enriquecer_com_summaries()
│
│  ── Configuração ────────────────────────────────────────────────────
├── config_portfolio.json        # GENÉRICO — contexto de infraestrutura (Stage 2 e 5) + catch-all universal
├── feedback_portfolio.json      # CURADORIA DA ÁREA — portfólio final + diretrizes + encaminhamentos (insumo do Stage 7)
├── requirements.txt             # Dependências Python para rodar localmente
├── AGENTS.md                    # Ponto de entrada operacional para IAs e novos mantenedores
├── CLAUDE.md                    # Ponte curta para AGENTS.md
│
│  ── Extração de dados do Jira ──────────────────────────────────────
├── extracao/
│   └── extrair_jira.py         # Lê os CSVs do Jira, limpa e exporta Extracao_Jira.xlsx
│
│  ── Pipeline offline (roda no HPC) ─────────────────────────────────
├── pipeline/
│   ├── llm_client.py           # Cliente HTTP para o Ollama — retry automático e parse de JSON
│   ├── 01_extract.py           # STAGE 1 — lê os CSVs, limpa e estrutura os tickets
│   ├── 02_summarize.py         # STAGE 2 — extrai intenção de cada ticket via LLM (etapa mais longa)
│   ├── 03_cluster.py           # STAGE 3 — agrupa tickets por similaridade semântica (bge-m3 + K-means); keywords extraídas dos campos 'tema' do Stage 2
│   ├── 04_label_clusters.py    # STAGE 4 — gera rótulos e metadados de cada grupo via LLM
│   ├── 05_compare_portfolio.py # STAGE 5 — compara grupos com portfólio atual e gera recomendação
│   ├── 06_classify_portfolio.py# STAGE 6 — classifica cada chamado histórico no portfólio otimizado via LLM
│   └── 07_finalize_portfolio.py# STAGE 7 — aplica a curadoria e reclassifica no portfólio final
│
│  ── Scripts HPC ────────────────────────────────────────────────────
├── hpc/
│   ├── submit_pipeline.sub     # Job PBS — submeter com qsub; despacha via mpirun para o nó GPU
│   ├── stage7.sub              # Job PBS do Stage 7 — curadoria final
│   ├── run_on_gpu.sh           # Executado no nó GPU via mpirun — inicia Ollama e roda os 6 stages
│   ├── run_stage7.sh           # Executado no nó GPU via mpirun — Ollama + Stage 7
│   └── setup_env.sh            # Configuração inicial do HPC (rodar uma única vez)
│
│  ── Dados do pipeline ──────────────────────────────────────────────
├── pipeline_data/
│   │
│   │  Arquivos intermediários (gitignored — contêm dados dos chamados)
│   ├── 01_tickets.json         # Saída do Stage 1 — tickets limpos e estruturados
│   ├── 02_checkpoint.json      # Estado do Stage 2 — permite retomada se interrompido
│   ├── 02_summaries.json       # Saída do Stage 2 — intenções extraídas pelo LLM
│   ├── 03_clusters.json        # Saída do Stage 3 — grupos com cluster_id por ticket
│   │
│   ├── 06_checkpoint.json      # Estado do Stage 6 — permite retomada se interrompido
│   ├── 06_classificados.json   # Saída do Stage 6 — classificação automática no portfólio otimizado
│   ├── 07_checkpoint.json      # Estado do Stage 7 — permite retomada se interrompido
│   ├── 07_classificados_final.json # Saída do Stage 7 — classificação no portfólio curado
│   │
│   │  Arquivos finais (VERSIONADOS — não contêm dados pessoais)
│   ├── 04_labels.json          # ★ SAÍDA FINAL — rótulos dos grupos, usado pelo dashboard
│   ├── 05_portfolio_recommendation.json  # ★ SAÍDA FINAL — recomendação automática do portfólio
│   └── 07_portfolio_final.json # ★ SAÍDA FINAL — portfólio final curado, quando houver
│
│  ── Interface web ──────────────────────────────────────────────────
├── templates/
│   └── index.html              # Single-page do dashboard (6 abas)
├── static/
│   ├── style.css               # Tema institucional FGV (light theme)
│   ├── script.js               # Lógica do dashboard e chamadas de API
│   └── vendor/
│       ├── chart.umd.min.js    # Chart.js — gráficos
│
│  ── Documentação ───────────────────────────────────────────────────
└── docs/
    ├── CONTEXTO_OBJETIVOS.md   # O que é o projeto e por que existe (contexto para LLMs)
    ├── GUIA_PROJETO.md         # Este arquivo — referência técnica completa
    ├── GUIA_EXTRACAO_JIRA.md   # Como exportar e tratar os CSVs do Jira
    ├── IDENTIDADE_VISUAL_FGV.md # Referência visual institucional
    ├── MANUAL_HPC.md           # Passo a passo de execução no HPC
    └── NOTAS_TECNICAS.md       # Decisões e inconsistências conhecidas
```

> **Regra de fonte ativa.** Os Stages 1–6 geram a recomendação automática. Quando `pipeline_data/07_portfolio_final.json` e `pipeline_data/07_classificados_final.json` existem, o dashboard, a simulação, o histórico e o mapeamento usam o portfólio curado do Stage 7. Se eles não existem, o app cai para a recomendação automática dos Stages 5/6.

---

## Arquivos de entrada necessários

### Para rodar o pipeline (HPC)

| Arquivo | Localização no HPC | Obrigatório | Descrição |
|---------|-------------------|:-----------:|-----------|
| `Extracao_Jira*.csv` | `~/triagem-chamados/data/` | ✅ | Exportação do Jira; separador `^`; não versionar |
| `config_portfolio.json` | `~/triagem-chamados/` | ✅ | Contexto da infraestrutura (`infra_context`) injetado nos Stages 2 e 5 + catch-all universal |
| `data_loader.py` | `~/triagem-chamados/` | ✅ | Lido pelo Stage 1 para carregar os CSVs |
| `pipeline/*.py` | `~/triagem-chamados/pipeline/` | ✅ | Scripts dos stages + `llm_client.py` |
| `hpc/submit_pipeline.sub` | `~/triagem-chamados/hpc/` | ✅ | Job PBS — submetido com `qsub`; despacha via mpirun |
| `hpc/run_on_gpu.sh` | `~/triagem-chamados/hpc/` | ✅ | Executado no nó GPU pelo mpirun — Ollama + 6 stages |
| `feedback_portfolio.json` | `~/triagem-chamados/` | Opcional para Stages 1–6; obrigatório no Stage 7 | Curadoria da área: portfólio final, diretrizes, fora-do-catálogo e encaminhamentos |
| `hpc/stage7.sub` + `hpc/run_stage7.sh` | `~/triagem-chamados/hpc/` | Obrigatório para Stage 7 | Job PBS e runner GPU da finalização curada |
| `venv/` | `~/triagem-chamados/` | ✅ | Ambiente Python com pandas, scikit-learn, numpy, requests |
| `~/.ollama/models/gemma4:26b-q8` | home do usuário | ✅ | Modelo LLM — ~20 GB |

### Para rodar o dashboard (local)

| Arquivo | Localização local | Obrigatório | Descrição |
|---------|------------------|:-----------:|-----------|
| `pipeline_data/04_labels.json` | raiz do projeto | ✅ | Alimenta a simulação com metadados de categorias (nomes, campos obrigatórios, SLA) |
| `pipeline_data/05_portfolio_recommendation.json` | raiz do projeto | ✅ | Recomendação automática; usada quando não há Stage 7 |
| `pipeline_data/07_portfolio_final.json` | raiz do projeto | Preferencial quando houver curadoria | Portfólio final definido pela área; vira fonte ativa do app |
| `pipeline_data/07_classificados_final.json` | raiz do projeto | Preferencial quando houver curadoria | Histórico reclassificado no portfólio final; vira fonte ativa do histórico e mapeamento |
| `Extracao_Jira*.csv` | pasta configurada em `JIRA_DATA_DIR` | Opcional | Necessário apenas para gerar/atualizar `knowledge_base.db` |
| `knowledge_base.db` | raiz do projeto | Opcional | Banco SQLite com estatísticas por categoria — gerado por `knowledge_base.py` |

> Se o banco não estiver disponível localmente, o dashboard abre com métricas vazias/zeradas. As abas **Análise IA** e **Simulação** continuam usando o portfólio ativo (`07_*` se existir; senão `05_*`). As abas **Dashboard**, **Categorias** e **Histórico** só mostram dados operacionais reais após gerar `knowledge_base.db`.

---

## Arquivos de saída esperados

O pipeline produz os seguintes arquivos em `pipeline_data/`. Os marcados com ★ devem ser copiados para o computador local após cada execução.

| Arquivo | Stage | Gitignored | Copiar local | O que contém |
|---------|:-----:|:----------:|:------------:|--------------|
| `01_tickets.json` | 1 | Sim | Opcional | Array de tickets limpos: id, resumo, descrição, categoria atual, situação, datas, comentários |
| `02_checkpoint.json` | 2 | Sim | Não | Progresso da sumarização — apagar antes de rodar do zero |
| `02_summaries.json` ★ | 2 | Sim | **Sim** | Tickets com campos adicionados pelo LLM: intenção, tema, tipo_pedido, contexto, info_fornecidas, info_faltantes, descricao_insuficiente — usado por `knowledge_base.py` para enriquecer o banco SQLite |
| `03_clusters.json` | 3 | Sim | Opcional | Tickets com cluster_id + estatísticas por cluster; contém amostras internas e não deve ser versionado |
| `04_labels.json` ★ | 4 | Não | **Sim** | Grupos rotulados: nome, descrição, quando_usar, informacoes_necessarias, SLA, complexidade |
| `05_portfolio_recommendation.json` ★ | 5 | Não | **Sim** | Diagnóstico, mapeamento atual→novo, portfólio otimizado, ações prioritárias, impacto estimado |
| `06_checkpoint.json` | 6 | Sim | Não | Progresso da classificação — apagar antes de rodar do zero |
| `06_classificados.json` ★ | 6 | Sim | **Sim** | Cada chamado com `categoria_nova`, `justificativa` e `confianca` — fallback do Histórico e mapeamento quando não há Stage 7 |
| `07_checkpoint.json` | 7 | Sim | Não | Progresso da reclassificação final — apagar se mudar o portfólio curado e quiser rodar do zero |
| `07_portfolio_final.json` ★ | 7 | Não | **Sim** | Portfólio final definido pela curadoria, com volumes e diretrizes aplicadas |
| `07_classificados_final.json` ★ | 7 | Sim | **Sim** | Cada chamado reclassificado no portfólio curado; tem prioridade sobre `06_classificados.json` no app |

---

## Fluxo de dados entre stages

Cada stage consome o output do anterior. Nenhum stage pode ser pulado.

```
Jira CSVs (data/)
    │
    ├──────────────────────────────────────────────┐
    ▼                                              ▼
[01_extract.py]                        [category_analyzer.py]
    │                                   (estatísticas do dashboard)
    ▼
pipeline_data/01_tickets.json
    │
    ▼
[02_summarize.py]  ←── 02_checkpoint.json (retomada automática se interrompido)
    │
    ▼
pipeline_data/02_summaries.json
    │                      │                      │
    ▼                      ▼                      ▼
[03_cluster.py]    knowledge_base.py     [06_classify_portfolio.py]  ←── 05_portfolio + config
    │              (enriquecer_com_        ←── 06_checkpoint.json
    │               summaries)                    │
    ▼                      │                      ▼
pipeline_data/         knowledge_base.db   06_classificados.json ★
03_clusters.json       (descricao_         (categoria_nova por ticket)
    │                   insuficiente)
    ├──────────────────────┐
    ▼                      ▼
[04_label_clusters.py]  [05_compare_portfolio.py]  ←── config_portfolio.json
    │                      │
    ▼                      ▼
04_labels.json ★    05_portfolio_recommendation.json ★
    │                      │
    └──────────┬───────────┘
               ▼
          app.py (Flask — dashboard e simulação LLM)
```

Após a curadoria humana, o Stage 7 roda em job separado (`qsub hpc/stage7.sub`), lendo `feedback_portfolio.json` e `02_summaries.json`. Ele gera `07_portfolio_final.json` e `07_classificados_final.json`; a partir daí esses arquivos têm prioridade sobre `05_portfolio_recommendation.json` e `06_classificados.json` no app.

---

## Schema dos arquivos de saída

### `02_summaries.json` — intenções extraídas pelo LLM

```json
[
  {
    "chave":                  "SDPESQ-XXXX",
    "intencao":               "frase objetiva do que o usuário quer",
    "tema":                   "2-3 palavras",
    "tipo_pedido":            "incidente|solicitacao|acesso|instalacao|duvida|configuracao|outro",
    "contexto":               "infraestrutura|nuvem|software|pesquisa|acesso|outro",
    "info_fornecidas":        ["informações já presentes no chamado"],
    "info_faltantes":         ["informações tipicamente necessárias mas ausentes"],
    "descricao_insuficiente": "sim|nao",
    "tipo_atual":             "categoria atual no Jira",
    "qtd_interacoes":         3,
    "situacao":               "Resolvido"
  }
]
```

> `descricao_insuficiente = "sim"` indica que o atendente precisou solicitar informações adicionais ao usuário nos comentários. Esta tag alimenta as métricas de qualidade de descrição no dashboard com mais precisão do que a contagem bruta de interações.

---

### `04_labels.json` — grupos naturais rotulados

```json
{
  "optimal_k": 25,
  "clusters": [
    {
      "cluster_id": 1,
      "nome": "Nome do Grupo",
      "descricao": "O que este grupo cobre.",
      "quando_usar": "Critério de seleção.",
      "informacoes_necessarias": ["campo 1", "campo 2"],
      "sla_sugerido": "1 dia útil",
      "complexidade": "baixa|media|alta",
      "total_tickets": 120,
      "volume_percentual": 9.0,
      "distribuicao_categorias_atuais": {"Categoria atual": 120},
      "rotulo_gerado_por_fallback": false
    }
  ]
}
```

### `05_portfolio_recommendation.json` — recomendação completa

```json
{
  "metadata": {
    "total_tickets": 0,
    "n_categorias_atuais": 0,
    "n_grupos_naturais": 0
  },
  "categorias_atuais": { "Nome Categoria": volume },
  "grupos_naturais": [ ],
  "recomendacao": {
    "diagnostico": "texto analítico",
    "problemas_encontrados": [
      { "problema": "...", "categorias_afetadas": [], "impacto": "..." }
    ],
    "mapeamento_atual_vs_natural": [
      { "categoria_atual": "...", "grupo_natural": "...", "confianca": "alta|media|baixa" }
    ],
    "portfolio_otimizado": [
      {
        "nome": "...",
        "descricao": "...",
        "quando_usar": "...",
        "informacoes_obrigatorias": [],
        "substitui_categorias_atuais": [],
        "volume_estimado_pct": 0.0,
        "sla_sugerido": "...",
        "complexidade": "...",
        "prioridade_implementacao": "alta|media|baixa"
      }
    ],
    "acoes_prioritarias": [
      { "acao": "...", "prazo": "...", "responsavel": "..." }
    ],
    "impacto_estimado": {
      "reducao_interacoes_multiplas": "...",
      "melhoria_tempo_resolucao": "...",
      "outros": "..."
    }
  }
}
```

---

## `config_portfolio.json` — referência

**Único arquivo de configuração do pipeline.** Contém duas seções principais:

### `infra_context.texto_contexto`
Texto injetado diretamente nos prompts do Stage 2 (análise por ticket) e Stage 5 (recomendação de portfólio). Descreve a infraestrutura da DTI, serviços disponíveis, softwares gerenciados, incidentes típicos e as categorias fixas do portfólio. É o contexto que orienta o LLM a classificar corretamente cada chamado.

Para atualizar: edite o campo `texto_contexto` em `config_portfolio.json` e transfira o arquivo para o HPC antes de re-executar.

### `categorias_obrigatorias`
Categorias genéricas que devem existir no portfólio recomendado independentemente dos dados. Hoje o padrão é manter aqui apenas o catch-all universal (`"Não encontrou o que procurava?"`). Categorias específicas da área devem ficar no `feedback_portfolio.json` e ser aplicadas pelo Stage 7.

```json
{
  "categorias_obrigatorias": [
    {
      "nome": "Nome da Categoria",
      "descricao": "O que esta categoria cobre.",
      "quando_usar": "Critério claro de seleção pelo usuário.",
      "informacoes_obrigatorias": ["Campo 1", "Campo 2"],
      "sla_sugerido": "1 dia útil",
      "complexidade": "baixa|media|alta",
      "prioridade_implementacao": "alta|media|baixa",
      "obrigatoria": true
    }
  ]
}
```

---

## Rodar o dashboard localmente

```bash
cd mba-ia-masterbi-puc
pip install -r requirements.txt

# Após copiar 02_summaries.json do HPC, popular o banco:
python knowledge_base.py

# Iniciar o dashboard:
python app.py
# Acesse http://localhost:5000
```

Variáveis de ambiente opcionais:

```powershell
# CSVs fora do diretório padrão (aponta para a pasta, não arquivos individuais):
$env:JIRA_DATA_DIR = "C:\caminho\para\pasta\com\csvs"

# Simulação via Azure OpenAI (opcional — se não configurada, só o modo LLM local fica disponível):
# Prefira usar o arquivo .env na raiz do projeto (não versionado):
# AZURE_OPENAI_API_KEY=sua-chave
# AZURE_OPENAI_ENDPOINT=https://seu-recurso.openai.azure.com/
# AZURE_OPENAI_DEPLOYMENT=gpt-4.1
# AZURE_OPENAI_API_VERSION=2025-01-01-preview

python app.py
```

---

## Stage 6 — Classificação dos chamados históricos no portfólio otimizado

O Stage 6 classifica cada chamado histórico em uma das categorias do portfólio otimizado (Stage 5), substituindo o mapeamento estatístico indireto por uma classificação real per-ticket via LLM.

**Motivação:** os Stages 3–5 produzem um mapeamento agregado (cluster → nova categoria) que indica tendências mas não classifica ticket a ticket. O Stage 6 resolve isso: cada chamado recebe uma categoria nova com justificativa e confiança, habilitando a visão de mapeamento detalhado no dashboard e a aba Histórico com dados reais.

**Por que usa `02_summaries.json` e não `01_tickets.json`:** o Stage 2 já extraiu a intenção, tema, tipo de pedido e contexto de cada chamado via LLM, com toda a análise do texto bruto. Reler título + descrição + comentários no Stage 6 seria redundante e tornaria o prompt ~10x maior. Usar o resumo já destilado produz classificações mais precisas com prompts menores e mais rápidos (~15–20 min vs ~60 min).

**Entradas:**
- `pipeline_data/02_summaries.json` — resumos extraídos pelo LLM no Stage 2
- `pipeline_data/05_portfolio_recommendation.json` — portfólio otimizado (Stage 5)
- `config_portfolio.json` — categorias obrigatórias

**Como classifica:** para cada chamado, o LLM recebe a intenção destilada (`intencao`, `tema`, `tipo_pedido`, `contexto`, `info_fornecidas`) e a lista de categorias do portfólio com descrições e critérios de uso. Escolhe a categoria mais adequada, justifica e atribui confiança.

**Saída:** `pipeline_data/06_classificados.json` — alimenta a aba **Histórico** e o **mapeamento detalhado** do dashboard quando o Stage 7 ainda não existe. Tem prioridade sobre o mapeamento por clusters, mas perde prioridade para `07_classificados_final.json` quando a curadoria final foi rodada.

Para rodar apenas o Stage 6 (sem re-executar os stages anteriores):
```bash
cd ~/triagem-chamados
venv/bin/python3 pipeline/06_classify_portfolio.py
```

### Schema do `06_classificados.json`

```json
[
  {
    "chave":          "SDPESQ-XXXX",
    "intencao":       "intenção extraída pelo Stage 2",
    "tipo_atual":     "categoria atual no Jira",
    "categoria_nova": "nome exato de uma categoria do portfólio otimizado",
    "justificativa":  "1-2 frases explicando a classificação",
    "confianca":      "alta|media|baixa"
  }
]
```

---

## Stage 7 — Finalização curada do portfólio

O Stage 7 aplica a decisão humana registrada em `feedback_portfolio.json`. Ele não inventa uma nova recomendação: usa o `portfolio_final`, as `diretrizes`, os itens `fora_do_catalogo` e os `encaminhamentos` definidos pela área para reclassificar os históricos.

**Entradas:**
- `feedback_portfolio.json` — portfólio final e regras de curadoria
- `pipeline_data/02_summaries.json` — resumos extraídos pelo LLM no Stage 2

**Saídas:**
- `pipeline_data/07_portfolio_final.json` — portfólio final com volumes consolidados
- `pipeline_data/07_classificados_final.json` — cada chamado classificado no portfólio curado
- `pipeline_data/07_checkpoint.json` — retomada do processamento

Quando `07_portfolio_final.json` e `07_classificados_final.json` estão presentes localmente, o `app.py` usa esses arquivos como fonte ativa para Análise IA, Categorias, Simulação, Histórico e mapeamento detalhado. Se eles não estão presentes, o app usa o recomendado automático dos Stages 5/6.

Para rodar apenas o Stage 7 depois da curadoria:
```bash
cd ~/triagem-chamados
qsub hpc/stage7.sub
```

---

## Rodar o pipeline no HPC

Resumo. Detalhes completos em [MANUAL_HPC.md](MANUAL_HPC.md).

1. **Verificar GPU disponível**: `ssh <no-gpu> "nvidia-smi | grep MiB"` — precisa de ~20 GB livres para `gemma4:26b-q8`
2. **Transferir arquivos atualizados** (scripts ou CSVs novos) via SCP
3. **Submeter**: `cd ~/triagem-chamados && qsub hpc/submit_pipeline.sub`
4. **Monitorar**: `tail -f ~/triagem-chamados/pipeline_data/pipeline.log`
5. **Copiar resultados** e limpar o HPC conforme [MANUAL_HPC.md — Limpeza pós-execução](MANUAL_HPC.md)

> Usar sempre `qsub`, nunca `bash submit_pipeline.sub`. O `bash` executa no head node sem GPU.

---

## Paralelismo no Stage 2

O Stage 2 usa configuração conservadora por padrão: `STAGE2_WORKERS=1` e `OLLAMA_NUM_PARALLEL=1`.

**VRAM:** `gemma4:26b-q8` é pesado para a V100 32 GB. Com `num_ctx=8192`, dois tickets simultâneos podem causar degradação, timeouts ou pressão de memória (OOM) na GPU. Por isso o padrão atual privilegia estabilidade em vez de velocidade.

> A forma de chamar o modelo (endpoint `/api/chat` + `think: false`) é independente do paralelismo e está documentada em [NOTAS_TECNICAS.md](NOTAS_TECNICAS.md).

Para testar mais desempenho, ajuste por variável de ambiente antes do `qsub`, com cautela:

```bash
export STAGE2_WORKERS=2
export STAGE6_WORKERS=2
export OLLAMA_NUM_PARALLEL=2
qsub hpc/submit_pipeline.sub
```

Se aparecer taxa alta de `_erro`, timeout ou mensagens de GPU/memória no `ollama.log`, volte para `1/1`.

---

## Variáveis de ambiente no HPC

Definidas em `hpc/submit_pipeline.sub`:

| Variável | Valor padrão | Descrição |
|----------|-------------|-----------|
| `OLLAMA_MODEL` | `gemma4:26b-q8` | Modelo LLM a usar |
| `OLLAMA_URL` | `http://localhost:11434` | Endereço do servidor Ollama |
| `OLLAMA_NUM_PARALLEL` | `1` | Quantidade de gerações simultâneas permitidas pelo Ollama |
| `STAGE2_WORKERS` | `1` | Quantidade de tickets processados simultaneamente no Stage 2 |
| `STAGE6_WORKERS` | `1` | Quantidade de tickets processados simultaneamente no Stage 6 |
| `JIRA_DATA_DIR` | `$HOME/triagem-chamados/data` | Pasta com os CSVs do Jira — todos os `Extracao_Jira*.csv` são carregados automaticamente |

---

## Adicionar um novo período de dados

1. Exportar o CSV do Jira para o novo período (mesmo formato e separador `^`)
2. Nomear o arquivo com prefixo `Extracao_Jira` (ex: `Extracao_Jira_2026.csv` ou `Extracao_Jira_lote_extra.csv`)
3. Transferir para `~/triagem-chamados/data/` no HPC
4. Apagar o checkpoint: `rm -f ~/triagem-chamados/pipeline_data/02_checkpoint.json`
5. Re-executar: `qsub hpc/submit_pipeline.sub`

O pipeline descobre automaticamente todos os `Extracao_Jira*.csv` na pasta `data/` — nenhuma edição de código necessária. Re-processa tudo do zero; não há merge incremental com execuções anteriores.
