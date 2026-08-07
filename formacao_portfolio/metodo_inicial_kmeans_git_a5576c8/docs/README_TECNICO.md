# Triagem Inteligente de Chamados — DTI FGV

> Sistema de análise e otimização do portfólio de serviços de TI com IA local — sem envio de dados para APIs externas.

---

## O Problema

A DTI da FGV atende centenas de chamados por mês classificados em 18 categorias. Porém, o portfólio foi definido com base na **intuição dos gestores**, não na análise sistemática do que os usuários realmente solicitam.

Isso gera três problemas concretos:
- **Categorias genéricas demais** — mesmo com 18 opções, o catch-all "Não encontrou o que procurava?" é a 3ª categoria mais usada (~13% dos chamados)
- **Múltiplas interações desnecessárias** — o chamado vai e volta por falta de informações iniciais
- **Métricas opacas** — sem visibilidade sobre tempo de resolução e volume real por tipo de demanda

## A Solução

Este sistema lê o histórico completo de chamados do Jira, usa um **modelo de linguagem rodando localmente no HPC da FGV** para entender o que cada usuário realmente pediu, descobre grupos naturais de demanda e compara com o portfólio atual — gerando recomendações concretas de otimização.

Como tudo roda no HPC interno da FGV, **nenhum dado sensível sai da infraestrutura institucional**.

---

## Como Funciona

### Pipeline de Análise (HPC)

O pipeline automático executa os Stages 1–6 no nó GPU do HPC. Depois da curadoria humana em `feedback_portfolio.json`, o Stage 7 reclassifica os históricos no portfólio final.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         PIPELINE (HPC — V100 32 GB)                          │
│                                                                              │
│  Stage 1    Stage 2        Stage 3          Stage 4    Stage 5    Stage 6   │
│  Extração → Sumarização → Clustering →    Rotulação → Comparação → Classif. │
│  ~30s       LLM (~2h)     bge-m3+K-means   ~10min     ~5min       ~20min    │
│             gemma4:26b-q8 ~15-20min         gemma4:26b-q8 em Stages 4-6      │
└──────────────────────────────────────────────────────────────────────────────┘
```

| Stage | O que faz |
|-------|-----------|
| **1 — Extração** | Lê os CSVs do Jira, limpa HTML/URLs/e-mails e estrutura os campos relevantes (título, descrição, comentários, categoria atual). Sem modelo. |
| **2 — Sumarização** | Para cada chamado, o LLM lê `título + descrição + comentários` e destila o que o usuário realmente quer: `intencao` (frase objetiva), `tema` (2-3 palavras), `tipo_pedido`, `contexto`, campos fornecidos e faltantes, e se o atendente precisou pedir informações adicionais (`descricao_insuficiente`). |
| **3 — Clustering** | Para cada ticket, combina `intencao + tema + tipo_pedido + contexto` e gera o embedding via `bge-m3`. Testa K de 5 a 25 via silhouette score e aplica K-means com o K ótimo. Keywords de cada grupo são os campos `tema` mais frequentes entre seus tickets — gerados pelo LLM no Stage 2, sem TF-IDF. |
| **4 — Rotulação** | Para cada grupo, o LLM recebe as intenções dos tickets mais próximos do centroide e define: nome, descrição, critério de uso (`quando_usar`), campos obrigatórios e SLA. |
| **5 — Comparação** | O LLM compara o portfólio atual do Jira (com volumes reais) com os grupos naturais + categorias obrigatórias definidas no `config_portfolio.json`, e gera o diagnóstico completo e o portfólio otimizado. |
| **6 — Classificação** | Para cada chamado, o LLM recebe o resumo já destilado no Stage 2 e a lista de categorias do portfólio otimizado, e atribui `categoria_nova`, `justificativa` e `confiança`. Alimenta a aba Histórico e o mapeamento detalhado do dashboard. |
| **7 — Finalização curada** | Lê `feedback_portfolio.json`, aplica o portfólio final e as diretrizes da área, e gera `07_portfolio_final.json` + `07_classificados_final.json`. Quando esses arquivos existem, eles viram a fonte ativa do app. |

> **Princípio central:** o LLM entende e destila cada chamado (Stage 2) → o embedding `bge-m3` agrupa por similaridade semântica real (Stage 3) → o LLM rotula, compara e reclassifica com contexto rico (Stages 4, 5, 6) → a curadoria humana consolida o portfólio final no Stage 7. Nenhum TF-IDF em nenhuma etapa.

### A jornada de um chamado (o que vira o quê)

Para entender o pipeline de verdade, acompanhe um chamado atravessando os estágios:

```
TEXTO BRUTO (Jira)
"Boa tarde, preciso usar o Stata mas não consigo conectar de casa"
      │
      ▼  Stage 2 — o LLM lê e destila em um resumo estruturado
RESUMO POR CHAMADO
  intencao: "Solicitar acesso à VPN acadêmica para usar o servidor Stata"
  tema: "Acesso VPN"
  tipo_pedido: "acesso"      ← etiqueta grossa (1 de 7 baldes fixos)
  contexto: "software"
      │
      ▼  Stage 3 — embedding bge-m3 + K-means agrupam por similaridade
GRUPO NATURAL
  "Acesso remoto / VPN"  (junto com outros ~80 chamados parecidos)
      │
      ▼  Stage 4 — o LLM dá nome, descrição, quando_usar, campos e SLA ao grupo
GRUPO ROTULADO
      │
      ▼  Stage 5 — o LLM faz a curadoria: funde/divide/renomeia grupos
      │            e injeta as categorias obrigatórias do config
CATEGORIA DO PORTFÓLIO RECOMENDADO   ← é AQUI que nasce a categoria futura
      │
      ▼  Stage 6 — cada chamado é reclassificado nessa categoria nova
CLASSIFICAÇÃO AUTOMÁTICA
      │
      ▼  Stage 7 — quando há curadoria, reclassifica no portfólio final da área
PORTFÓLIO ATIVO NO APP
```

### Três níveis de "classificação" que NÃO são a mesma coisa

É comum confundir os três — fixar a diferença ajuda a ler o dashboard corretamente:

| Nível | O que é | Quantos | Nasce em |
|-------|---------|---------|----------|
| `tipo_pedido` | etiqueta grossa por chamado (acesso, incidente, dúvida...) | **7 fixos** | campo do Stage 2 |
| **grupos naturais** | clusters por similaridade semântica do resumo inteiro | **5–25 (automático)** | Stage 3 |
| **portfólio otimizado** | categorias recomendadas para adoção | definido pelo LLM | Stage 5 |

Três pontos que evitam a confusão mais comum:

- **`tipo_pedido` não vira categoria.** É só um sinal auxiliar — entra no embedding do Stage 3 e dá uma visão macro no dashboard. Os 7 tipos *não* viram 7 grupos.
- **Os grupos não são 1-por-tipo.** Dois chamados `acesso` podem cair em grupos diferentes ("Acesso VPN" vs "Acesso a bases de dados"); um `incidente` e uma `solicitacao` sobre disco cheio podem cair no mesmo grupo. Quem decide é o **significado completo** do chamado — principalmente a `intencao`.
- **As categorias recomendadas nascem no Stage 5**, não no Stage 2. O LLM pode fundir, dividir e renomear os grupos naturais. Depois, quando houver Stage 7, a curadoria humana em `feedback_portfolio.json` passa a ser a fonte ativa do dashboard e da simulação.

### Dashboard (local)

Os resultados são visualizados em um dashboard Flask com 6 abas:

| Aba | O que mostra |
|-----|-------------|
| **Dashboard** | KPIs operacionais (volume, backlog, taxa de resolução, finalizados), filtro por mês, tendência mensal, top analistas, top solicitantes, por departamento e situação dos chamados |
| **Categorias** | Categorias atuais com estatísticas calculadas dos dados brutos + mapeamento para o novo portfólio |
| **Simulação** | Classifica um chamado fictício ou real no novo portfólio usando LLM Local (via túnel SSH para o HPC) ou Azure OpenAI |
| **Análise IA** | Diagnóstico completo: problemas do portfólio atual, portfólio otimizado, ações prioritárias e impacto estimado |
| **Histórico** | Chamados históricos reclassificados no portfólio ativo: Stage 7 curado quando existir; senão Stage 6 automático |
| **Grupos Naturais** | Grupos de demanda descobertos pelo pipeline, com volume, descrição, critério de uso e campos necessários |

---

## Resultado

Com a execução atual do Stage 7, o pipeline reclassificou **1.583 chamados** no portfólio final curado:

- **23 grupos naturais** de demanda vs 18 categorias atuais
- Portfólio final de **7 categorias** definido pela curadoria da área
- Maiores volumes: **Servidores Acadêmicos Compartilhados** (446), **Nuvem Pública** (431) e **Não encontrou o que procurava?** (247)
- Dashboard e simulação passam a usar esse portfólio final quando os arquivos `07_*` estão presentes

### O custo das idas e vindas (por que a triagem importa)

O script `analise_tempo_interacoes.py` compara o tempo de resolução dos chamados atendidos de forma **direta** (até 1 interação humana) com os que exigiram **múltiplas interações** (2+ trocas com o solicitante), ignorando comentários de automação. Na base real:

| Grupo | n | Média | Mediana |
|-------|---|-------|---------|
| Resolução direta (≤1 interação humana) | 333 | 2,5 dias | 0,4 dia |
| Múltiplas interações (≥2) | 1.228 | 13,9 dias | 5,7 dias |

Chamados que precisaram de idas e vindas levaram, **em média, ~5,5x mais tempo** para serem resolvidos. É essa evidência que motiva o assistente de triagem: um chamado aberto na categoria certa e com as informações completas tende à resolução direta.

```powershell
python analise_tempo_interacoes.py                      # base real (data/ ou JIRA_DATA_DIR)
python analise_tempo_interacoes.py --dados data_exemplo # base sintética versionada (15 chamados fictícios)
```

---

## Estrutura do Projeto

```
triagem-chamados-ia/
│
├── app.py                    # Servidor Flask — entry point do dashboard
├── data_loader.py            # Leitura e merge dos CSVs do Jira (auto-descobre Extracao_Jira*.csv)
├── knowledge_base.py         # Cria/popula o banco SQLite — rodar uma vez após clonar
├── category_analyzer.py      # Análise estatística de categorias
├── analise_tempo_interacoes.py  # Ganho de tempo: resolução direta vs múltiplas interações
│
├── config_portfolio.json     # GENÉRICO — contexto de infraestrutura (Stage 2 e 5) + catch-all universal
├── feedback_portfolio.json   # CURADORIA DA ÁREA — portfólio final + diretrizes + encaminhamentos (insumo do Stage 7)
├── requirements.txt          # Dependências Python
│
├── pipeline/                 # Scripts do pipeline HPC
│   ├── llm_client.py         # Cliente Ollama com retry e parse JSON
│   ├── 01_extract.py         # Stage 1: extração dos dados
│   ├── 02_summarize.py       # Stage 2: sumarização por LLM (com checkpoint)
│   ├── 03_cluster.py         # Stage 3: clustering bge-m3 + K-means
│   ├── 04_label_clusters.py  # Stage 4: rotulação dos grupos por LLM
│   ├── 05_compare_portfolio.py  # Stage 5: comparação e recomendação automática
│   ├── 06_classify_portfolio.py # Stage 6: reclassifica chamados históricos no recomendado automático
│   └── 07_finalize_portfolio.py # Stage 7: aplica curadoria e reclassifica no portfólio final
│
├── hpc/                      # Scripts PBS para o HPC FGV
│   ├── submit_pipeline.sub   # Job PBS (fila gpu) — submeter com qsub; despacha via mpirun
│   ├── stage7.sub            # Job PBS do Stage 7 — curadoria final
│   ├── run_on_gpu.sh         # Executado no nó GPU via mpirun — Ollama + Stages 1-6
│   ├── run_stage7.sh         # Executado no nó GPU via mpirun — Ollama + Stage 7
│   └── setup_env.sh          # Configuração inicial do HPC (rodar uma vez)
│
├── templates/
│   └── index.html            # Dashboard single-page
├── static/
│   ├── style.css
│   ├── script.js
│   └── vendor/               # Chart.js
│
├── extracao/
│   └── extrair_jira.py       # Script de extração e limpeza dos CSVs do Jira
│
├── data_exemplo/
│   └── Extracao_Jira_exemplo.csv  # Base sintética (15 chamados fictícios) — roda as análises sem dados reais
│
├── pipeline_data/            # Resultados do pipeline (parcialmente gitignored)
│   ├── 04_labels.json        # Grupos rotulados ← versionado
│   └── 05_portfolio_recommendation.json  # Recomendação automática ← versionado
│   # 06_classificados.json          # Classificação automática ← copiar do HPC, gitignored
│   # 07_portfolio_final.json        # Portfólio curado final ← copiar do HPC, agregado
│   # 07_classificados_final.json    # Classificação curada final ← copiar do HPC, gitignored
│
└── docs/
    ├── CONTEXTO_OBJETIVOS.md   # O que é o projeto e por que existe
    ├── GUIA_PROJETO.md         # Referência técnica completa
    ├── GUIA_EXTRACAO_JIRA.md   # Como exportar e tratar os dados do Jira
    ├── MANUAL_HPC.md           # Guia de execução no HPC
    └── NOTAS_TECNICAS.md       # Decisões e inconsistências conhecidas
```

---

## Instalação e Uso

### Pré-requisitos

- Python 3.10+
- Acesso ao HPC FGV (para rodar o pipeline)
- Resultados do pipeline em `pipeline_data/` (ver [Manual HPC](MANUAL_HPC.md))

### Configuração local (Windows — PowerShell)

```powershell
# 1. Clone o repositório e entre na pasta
git clone https://github.com/protasiofernando/mba-ia-masterbi-puc.git
cd mba-ia-masterbi-puc

# 2. Crie o ambiente virtual
python -m venv venv
venv\Scripts\activate

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Aponte para a pasta com os CSVs do Jira (dados sensíveis — não versionados)
$env:JIRA_DATA_DIR = "C:\caminho\para\pasta\com\csvs"
# O sistema detecta automaticamente todos os arquivos Extracao_Jira*.csv na pasta

# 5. (Opcional) Configure o Azure OpenAI para a aba Simulação
# Crie um arquivo .env na raiz do projeto (nunca versionar):
# AZURE_OPENAI_API_KEY=sua-chave
# AZURE_OPENAI_ENDPOINT=https://seu-recurso.openai.azure.com/
# AZURE_OPENAI_DEPLOYMENT=gpt-4.1
# AZURE_OPENAI_API_VERSION=2025-01-01-preview

# 6. Crie o banco de dados local (opcional; preenche Dashboard, Categorias e Histórico)
python knowledge_base.py

# 7. Suba o dashboard
python app.py
# Acesse: http://localhost:5000
```

> **Sobre o banco de dados**: `knowledge_base.db` não está versionado por conter dados dos chamados. É gerado localmente a partir dos CSVs do Jira pelo comando `python knowledge_base.py`. Sem ele o Flask inicia normalmente, mas as abas Dashboard e Categorias ficam sem dados.

O que funciona com apenas o repositório clonado (sem CSVs e sem banco):

| Aba | Sem banco | O que mostra |
|-----|:---------:|-------------|
| **Análise IA** | ✅ | Diagnóstico e portfólio ativo: Stage 7 curado quando existir; senão Stage 5 automático |
| **Grupos Naturais** | ✅ | Grupos de demanda com volume e metadados agregados |
| **Simulação** | ✅ | Classifica um chamado no novo portfólio (requer LLM local ou Azure OpenAI) |
| **Histórico** | ✅* | Lista vazia sem banco; reclassificação aparece com `knowledge_base.db` + `07_classificados_final.json` ou, na falta dele, `06_classificados.json` |
| **Dashboard** | ✅* | Abre com métricas zeradas sem banco; gráficos reais exigem `knowledge_base.db` |
| **Categorias** | ✅* | Abre vazia sem banco; estatísticas reais exigem `knowledge_base.db` |

### Usar o LLM Local na Simulação

A aba **Simulação** já tem o modo **LLM Local**. Para ele funcionar com o Flask rodando no seu PC, é preciso manter uma ponte SSH aberta para o Ollama no nó GPU:

```powershell
ssh -L 11434:localhost:11434 -J <seu.usuario>@<head-node> -N <seu.usuario>@<no-gpu>
```

Essa janela fica parada depois do login; isso é normal e indica que o túnel está ativo. O Ollama também precisa estar rodando no nó GPU. O passo a passo completo, incluindo como subir o Ollama com CUDA no V100 e testar `/api/ollama-status`, está em [docs/NOTAS_TECNICAS.md — Modo LLM Local](NOTAS_TECNICAS.md#modo-llm-local).

### Obter os dados do Jira

Os CSVs de entrada não estão versionados (dados sensíveis). Para obtê-los, consulte o guia completo de extração e tratamento:

📄 [docs/GUIA_EXTRACAO_JIRA.md](GUIA_EXTRACAO_JIRA.md)

Resumo: exporte os chamados do Jira usando a query JQL do guia, execute o script de tratamento e salve os CSVs com nomes iniciados por `Extracao_Jira` na pasta configurada. O sistema detecta automaticamente todos os arquivos compatíveis, independentemente do ano.

### Rodar o pipeline (HPC)

Consulte o [Manual de Uso no HPC](MANUAL_HPC.md) para o guia completo passo a passo.

Resumo:
```bash
# No head node do HPC
qsub hpc/submit_pipeline.sub

# Após conclusão, copie os resultados
HPC="<seu.usuario>@<head-node>"
scp "${HPC}:~/triagem-chamados/pipeline_data/04_labels.json" pipeline_data/
scp "${HPC}:~/triagem-chamados/pipeline_data/05_portfolio_recommendation.json" pipeline_data/
scp "${HPC}:~/triagem-chamados/pipeline_data/06_classificados.json" pipeline_data/
scp "${HPC}:~/triagem-chamados/pipeline_data/07_portfolio_final.json" pipeline_data/
scp "${HPC}:~/triagem-chamados/pipeline_data/07_classificados_final.json" pipeline_data/
```

Regra do dashboard: se `07_portfolio_final.json` e `07_classificados_final.json` estiverem presentes, eles são a fonte ativa. Se não estiverem, o app usa o recomendado automático dos Stages 5/6.

O pipeline usa `STAGE2_WORKERS=1`, `STAGE6_WORKERS=1` e `OLLAMA_NUM_PARALLEL=1` por padrão para manter o `gemma4:26b-q8` estável na V100 32 GB. Só aumente esses valores para teste controlado se o `ollama.log` não indicar timeout ou pressão de memória.

> **Uso do Ollama (vale para qualquer modelo):** o `pipeline/llm_client.py` chama o LLM pelo endpoint `/api/chat` e envia `think: false`. Modelos de raciocínio (como o `gemma4:26b-q8`) senão gastam o orçamento de tokens "pensando" e devolvem resposta vazia. Detalhes em [docs/NOTAS_TECNICAS.md](NOTAS_TECNICAS.md).

---

## Customização: `config_portfolio.json` (genérico) + `feedback_portfolio.json` (curadoria)

A adaptação a uma área se dá em **dois arquivos** com papéis distintos — o que mantém o pipeline 1–6 reaproveitável em qualquer área.

### `config_portfolio.json` — genérico (pipeline 1–6)
- **`infra_context.texto_contexto`**: descreve a infraestrutura, serviços, softwares e incidentes típicos da área. Injetado nos prompts do Stage 2 (por ticket) e Stage 5 (recomendação) — é o contexto que orienta o LLM. Edite e transfira para o HPC antes de re-executar.
- **`categorias_obrigatorias`**: mantém apenas o catch-all universal (`"Não encontrou o que procurava?"`). As categorias fixas específicas da área **não** ficam aqui — vão para a curadoria.

### `feedback_portfolio.json` — curadoria da área (insumo do Stage 7)
Preenchido pelo dono da área **depois** de revisar a recomendação automática (Stage 5). Define:
- **`portfolio_final`**: as categorias definitivas, cada uma com `quando_usar` rico — é o texto que guia a reclassificação e a simulação
- **`diretrizes`**: regras transversais (ex: "acesso classifica pelo ambiente-alvo; armazenamento é atributo do ambiente")
- **`fora_do_catalogo`**: serviços de outra área → "Não encontrou" com explicação (ex: SharePoint/M365)
- **`encaminhamentos`**: demandas de outra equipe (ex: Sala de Sigilo → Segurança)

O **Stage 7** (finalização) lê este arquivo e reclassifica os históricos no `portfolio_final`, deixando o dashboard e a simulação consistentes com o portfólio que a área escolheu como ideal.

Após qualquer edição, transfira o arquivo para o HPC e re-submeta o job.

---

## Infraestrutura

| Componente | Especificação |
|------------|---------------|
| HPC Head Node | `<head-node>` |
| Nó GPU | Tesla V100 PCIE 32 GB — CUDA 13.0 |
| Modelo LLM | `gemma4:26b-q8` via [Ollama](https://ollama.com) |
| Embedding | `bge-m3` via Ollama (Stage 3) |
| Scheduler | PBS (fila `gpu`) |
| Backend | Flask 3.x + SQLite |
| Frontend | HTML/CSS/JS + Chart.js |

---

## Dados e Privacidade

Os arquivos CSV exportados do Jira contêm dados pessoais de usuários e **não devem ser versionados**. O `.gitignore` já exclui:

- `data/*.csv` — exportações do Jira
- `*.db` — banco SQLite com dados dos chamados
- `pipeline_data/02_summaries.json` — intenções extraídas (contêm texto dos chamados)
- `pipeline_data/06_classificados.json` — chamados reclassificados automaticamente no Stage 6 (contêm dados individuais)
- `pipeline_data/07_classificados_final.json` — chamados reclassificados no portfólio curado do Stage 7 (contêm dados individuais)

Os arquivos versionados (`04_labels.json`, `05_portfolio_recommendation.json`) contêm apenas metadados agregados e recomendações estruturais, sem dados pessoais.

---

## Licença

MIT — ver [LICENSE](../LICENSE).
