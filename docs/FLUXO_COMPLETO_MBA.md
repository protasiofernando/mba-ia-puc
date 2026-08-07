# Fluxo completo do MBA: dos chamados à comparação de métodos

Este é o documento canônico para explicar, de forma técnica e lógica, o fluxo
completo do projeto. Ele responde a quatro perguntas:

1. Como os chamados históricos viram evidência estruturada de demanda?
2. Como essa evidência produz uma proposta de portfólio?
3. Onde entra a curadoria estratégica que define o portfólio adotado?
4. Como métodos diferentes são comparados de maneira justa contra essa decisão?

Os comandos operacionais continuam no `README_TECNICO.md` e no
`../estudo_comparativo/RUNBOOK_HPC.md`. O protocolo estatístico detalhado está
em `../estudo_comparativo/PROTOCOLO_METODOLOGICO.md`.

## 1. Objetivo e resposta produzida pelo projeto

O objetivo geral é propor o portfólio de serviços que melhor atende às demandas
reais da DTI Pesquisa e definir quais informações o pesquisador deve fornecer ao
abrir cada chamado.

O projeto não trata “portfólio ótimo” como um resultado puramente matemático.
Há duas camadas complementares:

- **evidência empírica:** frequência, intenção, tratamento, sobreposição,
  lacunas, ambiguidade e informações historicamente fornecidas ou ausentes;
- **decisão gerencial:** responsabilidade técnica, governança, visibilidade,
  segurança, operabilidade, navegação e estratégia institucional.

Por isso, a saída adotada é o portfólio curado em
`formacao_portfolio/decisao_curada/feedback_portfolio.json`.
Os métodos automáticos produzem recomendações e evidências; a gestão decide.

O portfólio vigente possui:

- sete serviços substantivos;
- um item residual de triagem, “Não encontrou o que procurava?”;
- Sala de Sigilo como item fixo e visível, fora da análise e atendido pela
  Segurança da Informação.

## 2. Três fases que não devem ser misturadas

```text
FASE A — formação assistida do candidato

CSV Jira
  -> filtro de escopo quando aplicável
  -> Stage 1: extrair e limpar
  -> Stage 2: destilar intenção
  -> Stage 3 estatístico: bge-m3 + K-means
  -> Stage 4: rotular grupos
  -> Stage 5: recomendar portfólio
  -> Stage 6: reclassificar o histórico
  -> candidato automático + evidências

FASE B — decisão operacional

candidato automático
  -> curadoria humana no nível do catálogo
  -> formacao_portfolio/decisao_curada/feedback_portfolio.json
  -> projeção analítica determinística
  -> formacao_portfolio/decisao_curada/portfolio_referencia.json congelado
  -> Stage 7: classificação automática no portfólio adotado

FASE C — contribuição metodológica do MBA

Stage 2 congelado + portfólio curado congelado
  -> job 00: referência automática independente dos braços
  -> benchmark: arquitetura legada versus arquitetura nativa
  -> ablação: K-means versus LLM com restante comum
  -> três seeds + quatro visões de referência + camadas
  -> job 90: métricas, incerteza, custo e auditoria dos campos
  -> conclusão metodológica pré-registrada
```

A Fase A produz evidência e um candidato; a Fase B responde “qual solução foi
adotada?”; a Fase C responde “quanto cada abordagem automática reconstrói essa
decisão, com que estabilidade e custo?”. A comparação não substitui a curadoria.

Essa ordem é comprovável: o commit `a5576c8` já contém o Stage 3 com `bge-m3`
e K-means, os Stages 4–6 e um Stage 7 que lê a curadoria humana. A versão
mantida do processo está em `../formacao_portfolio/`. O Método Estatístico foi,
portanto, usado para formar o candidato e depois reexecutado, junto com o Método
Agêntico, como objeto de avaliação. O alvo é ex post em relação à formação e ex
ante em relação aos braços comparativos.

O mesmo commit contém a cadeia de artefatos: recomendação automática com dez
itens, `feedback_portfolio.json` curado para sete e `07_portfolio_final.json`
materializado. O portfólio vigente evoluiu depois com Acesso a Bases como
serviço próprio e Sala de Sigilo como encaminhamento fixo. Os totais antigos de
Stage 5 (1.575) e Stage 7 (1.583) não coincidem; por isso servem como prova da
cronologia, não como fonte quantitativa do estudo, que usa exclusivamente o
corpus limpo e congelado de 1.456.

Nesse commit, o candidato do Stage 5 registra 1.575 chamados, 23 grupos naturais
e 10 itens sugeridos; o Stage 7 materializa 1.583 chamados em sete categorias
da primeira curadoria. O alvo final do estudo é uma evolução gerencial dessa
versão: inclui “Solicitação de Acesso a Bases de Dados” e mantém Sala de Sigilo
como encaminhamento fixo fora da análise. Essa evolução fica registrada como
curadoria estratégica, não como saída automática de um método.

## 3. Stage não é job

Um **stage** é uma transformação analítica com entrada e saída definidas.

Um **job** é um processo submetido ao PBS no HPC. Ele reserva recursos, sobe o
Ollama, congela ou verifica o ambiente, mede tempo/tokens/GPU, executa um ou
mais stages e aplica gates.

Exemplos:

- `scripts/hpc/job_pipeline.sh` executa os Stages 1 a 6 do pipeline operacional;
- `formacao_portfolio/hpc/job_formar_candidato_estatistico.sh` reproduz a
  formação do candidato sem escrever a decisão humana;
- `scripts/hpc/job_stage7_curadoria.sh` aplica automaticamente a decisão
  congelada aos chamados;
- `job_00_referencia.sh` não é “Stage 0”: ele prepara a referência e valida o
  experimento;
- `job_30_ablacao.sh` executa os Stages 3 a 6 de um braço controlado;
- `job_90_avaliacao.sh` não descobre grupos: ele valida e compara resultados.

## 4. Entradas e governança dos dados

### 4.1 Entradas de negócio

- `configuracao/projeto.json`: identidade do portal e padrão dos CSVs;
- `configuracao/config_portfolio.json`: contexto institucional e restrições;
- `configuracao/contexto_catalogo.md`: catálogo real fornecido pela área;
- `formacao_portfolio/decisao_curada/feedback_portfolio.json`: decisão final;
- `formacao_portfolio/decisao_curada/portfolio_referencia.json`: espelho
  congelado dessa decisão para avaliação.

O catálogo real não é inferido dos CSVs. Ele é insumo institucional.

### 4.2 Dados históricos

Os CSVs exportados do Jira contêm título, descrição, comentários, request type,
situação, datas e quantidade de interações. São dados sensíveis e permanecem na
infraestrutura institucional.

O Stage 1 remove HTML, URLs e e-mails, mas isso não transforma o conjunto em
dado público. Artefatos por chamado continuam privados.

### 4.3 Universo da comparação

O universo original tinha 1.584 chamados. Antes do Stage 1, 128 registros
foram removidos por correspondência determinística no campo estruturado
`Customer Request Type`. Restaram 1.456.

O filtro:

- não lê descrição nem comentário;
- não usa LLM;
- aplica a lista e os hashes de
  `../estudo_comparativo/filtro_sala_sigilo_manifest_v6.json`;
- ocorre antes de qualquer método avaliado.

Sala de Sigilo continua visível no portfólio, mas não entra em descoberta,
referência, métrica ou ranking.

Uma demanda textual sobre acesso a dados não é automaticamente Sala. O que
define a exclusão é o request type estruturado congelado no manifesto. Por isso,
o portfólio analítico ainda pode conter um serviço de acesso a bases para
demandas remanescentes que pertençam à DTI Pesquisa.

## 5. Pipeline operacional, Stage por Stage

### 5.1 Stage 1 — extração e limpeza determinística

**Pergunta respondida:** quais registros possuem conteúdo utilizável e qual é a
representação estruturada mínima de cada chamado?

**Implementação:** `../scripts/extract.py`.

**Entrada:** CSVs em `data/`.

**Processamento:**

- carrega e padroniza colunas do Jira;
- limpa HTML, URLs, e-mails e espaços;
- limita descrições e comentários a tamanhos controlados;
- reconstrói título quando a limpeza o deixou vazio;
- preserva a chave para rastreabilidade interna;
- calcula texto completo, situação, request type histórico e interações;
- descarta somente registros sem conteúdo textual útil.

**Saída:** `pipeline_data/01_tickets.json`.

**Natureza:** Python determinístico, sem LLM.

**Relação com o objetivo:** cria uma base uniforme e auditável, sem ainda tomar
decisão sobre portfólio.

**Controle:** contagens, campos presentes e cardinalidade são registrados no
log. Na execução analisada foram produzidos 1.456 registros.

### 5.2 Stage 2 — destilação da intenção por chamado

**Pergunta respondida:** o que o usuário realmente queria, independentemente da
categoria em que abriu o chamado?

**Implementação:** `../scripts/run_stage2_llm.py`.

**Entrada:** `01_tickets.json`.

**Modelo vigente:** `llama3.3:70b`, local via Ollama.

**Campos enviados ao modelo:** título, descrição e comentários, mais contexto
institucional do portal.

**Proteção contra viés histórico:** o request type antigo não é mostrado no
prompt. Ele pode ser preservado na saída para auditoria, mas não orienta a
destilação.

**Campos produzidos por chamado:**

- `intencao`: pedido ou problema em frase objetiva;
- `tema`: resumo curto do assunto;
- `tipo_pedido`: incidente, solicitação, acesso, instalação, dúvida,
  configuração ou outro;
- `contexto`: domínio curto do portal;
- `info_fornecidas`: até três informações já presentes;
- `info_faltantes`: até três informações tipicamente necessárias;
- `descricao_insuficiente`: evidência de que o atendente precisou pedir dados.

**Saída:** `pipeline_data/02_summaries.json`.

**Relação com o objetivo:** separa a demanda real da estrutura antiga do
catálogo e cria a matéria-prima para descobrir serviços e desenhar formulários.

**Controle:**

- contrato `intent-blind-v2`;
- temperatura congelada na comparação;
- checkpoint por modelo e hash da fonte de cada chamado;
- JSON inválido recebe retry;
- o arquivo final só é gravado quando todos os registros estão resolvidos.

O Stage 2 foi congelado com 1.456 registros e SHA-256
`e4fb8e41c910f8f2ed6151d8e69515ae8fd1b01f1310d47fa680d4403fd54ff1`.

### 5.3 Stage 3 — descoberta dos grupos naturais

**Pergunta respondida:** quais demandas exigem tratamento, equipe, autorização,
formulário ou fluxo diferentes?

Há dois motores de descoberta.

#### Motor LLM nativo

**Implementação:** `../scripts/run_stage3_llm.py`.

**Modelo semântico:** `llama3.3:70b`.

**Compilador JSON:** `qwen3:30b-a3b-instruct-2507-q4_K_M`.

**Processamento hierárquico:**

1. divide intenções em lotes reprodutíveis;
2. propõe grupos locais pelo tratamento necessário, não por palavra;
3. atribui cada demanda a um ID local fechado;
4. preserva casos que não cabem como avulsos, sem forçá-los ao primeiro grupo;
5. redescobre recursivamente avulsos quando há massa semântica;
6. consolida grupos locais numa taxonomia global;
7. atribui novamente todas as demandas à taxonomia fechada;
8. mantém residual técnico quando não há pertencimento seguro.

O residual `outlier_residual` é instrumento técnico e não pode virar serviço
publicável.

Na descoberta e na atribuição não entram `tipo_atual` nem o `contexto` inferido.
O contrato comum usa intenção, tema e tipo de pedido.

#### Motor estatístico

**Implementação controlada:** `../scripts/run_stage3_kmeans_fair.py`.

**Processamento:**

1. monta texto com `intencao + tema + tipo_pedido`;
2. gera embeddings com `bge-m3`;
3. normaliza os vetores;
4. testa `K=4..30`;
5. executa K-means com `n_init=20` e seed congelada;
6. escolhe o maior silhouette score;
7. em empate no sexto decimal, escolhe o menor K;
8. atribui cada chamado ao centroide mais próximo.

Essa regra escolhe K sem consultar o portfólio-alvo.

**Saída dos motores:** `pipeline_data/03_clusters.json`, contendo atribuição por
chamado, estatísticas dos grupos, amostras e metadados.

**Relação com o objetivo:** descobre a estrutura latente das demandas antes de
confrontá-la com o catálogo real.

### 5.4 Interface comum da ablação

Na comparação justa, a saída bruta do Stage 3 é passada por
`../scripts/normalizar_stage3_comum.py`.

O normalizador:

- preserva a saída bruta em `03_clusters_raw.json`;
- remove definições autorais específicas de cada motor;
- remove `contexto`, `tipo_atual` e distribuição de categorias antigas;
- remapeia IDs arbitrários por assinatura determinística dos membros;
- reconstrói amostras e estatísticas com a mesma regra;
- entrega ao Stage 4 apenas a partição produzida pelo motor.

Isso impede que o braço LLM leve para o Stage 4 descrições mais ricas que o
K-means não poderia produzir.

### 5.5 Stage 4 — rotulagem dos grupos descobertos

**Pergunta respondida:** como cada grupo natural deve ser apresentado em
linguagem de serviço?

**Implementação:** `../scripts/run_stage4_llm.py`.

**Entrada:** `03_clusters.json`, contexto do portal e catálogo real.

**Modelo:** `llama3.3:70b`.

**Produção por grupo:**

- nome orientado ao usuário;
- descrição;
- critério de quando usar;
- informações necessárias;
- SLA sugerido;
- complexidade;
- volume e distribuição observada.

**Saída:** `pipeline_data/04_labels.json`.

**Relação com o objetivo:** transforma partições técnicas em candidatos
compreensíveis e começa a responder quais dados um formulário deve solicitar.

**Controle:** checkpoint vinculado ao modelo e ao fingerprint do Stage 3;
campos obrigatórios validados; até três tentativas; nenhuma saída parcial é
publicada como completa.

No benchmark nativo o Stage 4 pode receber o contexto rico do pipeline
operacional. Na ablação, ambos os motores recebem estritamente a interface
comum descrita na seção anterior.

### 5.6 Stage 5 — reconciliação e recomendação de portfólio

**Pergunta respondida:** como converter grupos naturais em um catálogo
implementável, comparando-os com o catálogo existente?

**Implementação:** `../scripts/run_stage5_llm.py`.

**Entradas:**

- grupos rotulados do Stage 4;
- catálogo real em `configuracao/contexto_catalogo.md`;
- contexto e restrições em `configuracao/config_portfolio.json`;
- categorias obrigatórias declaradas pela área.

**Modelos:**

- Llama para decisão semântica;
- Qwen para compilar o plano em JSON estrito;
- Python para contagens, IDs, cobertura, fingerprints e montagem final.

**Processamento lógico:**

1. produz um rascunho-base de portfólio;
2. cria um candidato de request type para cada grupo natural;
3. reconcilia candidatos que compartilham ou não fluxo operacional;
4. mantém separados serviços com sistema, equipe, aprovação, formulário, SLA
   ou segurança diferentes;
5. permite que request types distintos compartilhem um agrupador lógico;
6. evita aumentar grupos de navegação sem justificativa;
7. audita propostas de fusão;
8. avalia categorias atuais contra a demanda;
9. avalia candidatos raros e residuais;
10. monta deterministicamente a recomendação e os diagnósticos.

**Saída:** `pipeline_data/05_portfolio_recommendation.json`.

O artefato contém:

- análise geral;
- problemas encontrados;
- mapeamento catálogo atual versus grupos naturais;
- reconciliação;
- grupos de navegação;
- portfólio otimizado proposto;
- campos obrigatórios;
- SLA e complexidade;
- avaliação de outliers;
- ações prioritárias e impacto estimado.

**Relação com o objetivo:** é a recomendação automática de redesign, já
traduzida em unidades operacionais e formulários.

**Controle:** o validador recusa, entre outros problemas:

- item sem demanda histórica, salvo regra institucional explícita;
- categoria atual inventada;
- perda de grupo natural;
- item `manter_separado` sem evidência correspondente;
- fingerprint incompatível com o Stage 4;
- Sala indevidamente incluída no universo analítico.

### 5.7 Stage 6 — classificação fechada no portfólio recomendado

**Pergunta respondida:** o portfólio proposto consegue receber todos os chamados
históricos de forma rastreável?

**Implementação:** `../scripts/run_stage6_llm.py`.

**Entrada:** `02_summaries.json` e o portfólio fechado do Stage 5.

**Modelo:** `llama3.3:70b`.

Para cada chamado, a LLM retorna somente:

- `category_id` existente;
- segunda opção opcional;
- justificativa;
- confiança;
- ambiguidade.

O Python deriva nome e grupo a partir do ID fechado. A categoria antiga do Jira
não é enviada ao modelo.

**Saídas:**

- `pipeline_data/06_classificados.json`, privado e por chamado;
- `pipeline_data/06_quality_report.json`, agregado e versionável.

**Relação com o objetivo:** testa cobertura, sobreposição e ambiguidade do
portfólio proposto e fornece a distribuição usada no dashboard.

**Controle:** até três tentativas semânticas; ID inventado é rejeitado; não há
fallback para a primeira categoria; o arquivo final exige cobertura completa.

### 5.8 Stage 7 — curadoria estratégica

**Pergunta respondida:** qual configuração será adotada pela organização,
considerando evidência e decisão de gestão?

**Fonte canônica:**
`../formacao_portfolio/decisao_curada/feedback_portfolio.json`.

A curadoria pode:

- manter ou fundir sugestões;
- ajustar nomes e descrições;
- definir grupos de navegação;
- congelar informações obrigatórias, SLA e complexidade;
- preservar serviços estratégicos de baixo volume;
- manter encaminhamentos por responsabilidade ou governança;
- preservar Sala de Sigilo como item visível e imutável.

O resultado atual tem nove itens: sete serviços substantivos, o catch-all e
Sala de Sigilo.

`../formacao_portfolio/decisao_curada/portfolio_referencia.json` não é uma
segunda curadoria. É o espelho
estruturado usado pela comparação:

- oito categorias analíticas, incluindo o catch-all;
- Sala de Sigilo em `itens_fixos_fora_analise`.

**Implementação:** `scripts/materializar_portfolio_curado.py` valida a
equivalência entre a decisão humana e o espelho analítico sem alterar os
arquivos congelados. `scripts/run_stage7_curadoria.py` classifica os 1.456
resumos automaticamente em IDs fechados, e
`scripts/hpc/job_stage7_curadoria.sh` orquestra a execução no HPC. O dashboard
prefere o agregado `07_*` e, antes que ele exista, lê diretamente
`formacao_portfolio/decisao_curada/feedback_portfolio.json`; portanto nunca
apresenta o candidato do Stage 5 como
se fosse a decisão final.

Não houve rotulagem humana por chamado. A intervenção humana ocorreu somente
no nível do catálogo; tanto a referência do estudo quanto a projeção Stage 7
por chamado são automáticas.

Depois do encerramento do estudo, essa projeção operacional foi materializada
sobre os 1.456 chamados. O agregado público contém 455 classificações em
Servidores Acadêmicos, 426 em Nuvem Pública, 246 em Softwares e Licenças, 98
em Máquinas Virtuais, 95 em HPC, 65 em Acesso a Bases, 48 em PGD e 23 no item
residual. Sala de Sigilo não recebeu classificação e continua fora da análise.
Esses volumes são retrospectivos e não medem adoção futura do portal.

## 6. Como os stages respondem ao objetivo do MBA

| Objetivo específico | Evidência produzida |
|---|---|
| Entender demanda real sem reproduzir o catálogo antigo | Stage 2 |
| Descobrir agrupamentos naturais | Stage 3 |
| Tornar grupos compreensíveis e operacionais | Stage 4 |
| Diagnosticar catálogo e propor redesign | Stage 5 |
| Testar cobertura e ambiguidade | Stage 6 |
| Incorporar estratégia e governança | Stage 7 |
| Definir o que o usuário deve informar | Stages 2 e 4, curadoria do Stage 7 e auditoria do job 90 |
| Justificar a escolha de abordagem | benchmark, ablação, robustez e custo |

## 7. Preparação específica da comparação robusta

### 7.1 Regeneração dos Stages 1 e 2

A preparação executou, em diretório isolado:

1. validação dos três CSVs filtrados;
2. Stage 1 sobre 1.456 chamados;
3. Stage 2 com Llama;
4. registro de modelo, digest, temperatura, código, cardinalidade e hashes.

Produziu o Stage 2 congelado usado por todos os braços. Nenhum braço pode
regenerá-lo ou alterá-lo.

### 7.2 Pacote code-only e ambiente

O ZIP final:

- contém somente código, configuração e protocolo;
- não contém CSV, Stage 1, Stage 2, checkpoint ou texto por chamado;
- recebe o Stage 2 por cópia server-side dentro do HPC;
- registra manifesto com SHA de cada arquivo.

O job 00 congela ainda:

- versões Python e bibliotecas;
- configuração NumPy/BLAS;
- GPU e driver;
- digests dos modelos Ollama;
- proveniência do código.

## 8. O que faz cada job da comparação

### 8.1 Job 00 — referência automática e gate de setup

**Script:** `../estudo_comparativo/hpc/job_00_referencia.sh`.

**Execução:** cada release válida começa em workspace limpo e congela seu ambiente.

**Funções:**

1. valida SHA, cardinalidade e schema do Stage 2;
2. materializa uma máscara que inclui todos os 1.456 registros;
3. confirma zero exclusões internas e zero decisão de escopo por LLM;
4. sobe Ollama e congela o ambiente;
5. constrói a referência automática contra o portfólio curado;
6. distribui cópias byte a byte do mesmo Stage 2 aos oito braços;
7. valida pacote, escopo, referência, ambiente, ordem das chaves e entradas.

#### Como a referência é construída

Llama e Qwen classificam cada demanda no portfólio analítico fechado:

- não recebem a chave Jira real, somente identificador opaco;
- não recebem a categoria histórica;
- recebem apenas o Stage 2 e o portfólio-alvo;
- fazem uma passagem inicial com ordens diferentes das categorias;
- desacordos, ambiguidade ou baixa confiança recebem retestes;
- maioria estável de três em quatro define cobertura quando disponível;
- casos restantes recebem um “chair” automático, alternado por hash;
- a referência estrita mantém apenas acordo inicial limpo;
- a referência completa cobre os 1.456 registros.

#### Protocolo de votação `a1`/`b1`/`a2`/`b2`

| Passagem | Modelo | Registros | Ordem das categorias | Função |
|---|---|---:|---|---|
| `a1` | Llama | todos os 1.456 | normal | primeira projeção independente |
| `b1` | Qwen | todos os 1.456 | reversa | segunda projeção independente e controle de viés de posição |
| `a2` | Llama | somente casos difíceis de `a1/b1` | rotacionada | reteste de estabilidade, reavaliado do zero |
| `b2` | Qwen | o mesmo subconjunto de `a2` | normal | reteste de estabilidade, reavaliado do zero |
| `chair_a` ou `chair_b` | Llama ou Qwen | somente casos sem maioria 3 de 4 | rotacionada | desempate automático final, decidido do zero |

Um chamado entra simultaneamente em `a2` e `b2` quando pelo menos uma das
condições abaixo ocorre em `a1/b1`:

```text
decision_id(a1) != decision_id(b1)
OU confidence(a1) == "baixa"
OU confidence(b1) == "baixa"
OU ambiguity(a1) == true
OU ambiguity(b1) == true
```

Portanto, `b2` não é apenas uma revisão dos casos em que o Qwen declarou baixa
confiança. É uma nova avaliação do Qwen sobre todo caso considerado instável
por qualquer um dos dois modelos ou pelo desacordo entre eles. `a2` e `b2`
recebem exatamente o mesmo subconjunto. Nenhum reteste recebe os votos
anteriores nem a resposta do outro modelo; a instrução explícita é reavaliar do
zero.

#### Formação do consenso

1. **Consenso estrito:** existe apenas quando `a1` e `b1` escolhem o mesmo ID,
   nenhum marca ambiguidade e nenhum declara confiança baixa. Confiança média é
   aceita; baixa não.
2. **Acordo inicial para cobertura:** se o caso não precisa de reteste, o acordo
   `a1/b1` define a categoria de cobertura com força 2.
3. **Maioria de estabilidade:** nos casos retestados, contam-se os quatro IDs
   de `a1`, `b1`, `a2` e `b2`. A categoria precisa obter pelo menos três dos
   quatro votos, sem empate.
4. **Chair automático:** se não houver maioria 3 de 4, um único modelo é
   escolhido deterministicamente pelo SHA-256 do identificador interno do
   registro: par direciona ao Llama; ímpar, ao Qwen. Esse modelo decide do zero
   com ordem rotacionada. Não há escolha humana de qual modelo desempata.
5. **Confiança do consenso:** é derivada das confianças dos votos que apoiam a
   categoria final: alta se todos forem altos, baixa se algum for baixo e média
   nos demais casos.

O identificador usado para distribuir o chair é interno e opaco. A chave Jira
real e a categoria histórica não são mostradas aos modelos. Cada voto
persistido registra modelo, passagem, ID escolhido, confiança e ambiguidade.

As quatro visões usadas na análise são:

- `consensus_strict`: somente o consenso inicial limpo; pode não cobrir todo o
  universo;
- `consensus_full`: maioria 3 de 4 ou chair, cobrindo os 1.456 registros;
- `model_a`: primeira decisão do Llama (`a1`);
- `model_b`: primeira decisão do Qwen (`b1`).

As quatro visões são mantidas separadas para verificar se a conclusão sobre os
métodos depende da forma de construir a referência. O chair garante cobertura,
mas não transforma a referência automática em verdade humana independente.

**Saídas principais:**

- `referencia/01_scope_mask.json`;
- `referencia/02_summaries_escopo.json`;
- `referencia/06_referencia_consenso.json`;
- `referencia/06_referencia_quality.json`;
- `manifesto_insumo_comum.json`;
- `AMBIENTE_CONGELADO.json`;
- `avaliacao/VALIDACAO_SETUP.json`.

Na execução final, o setup foi congelado e validado antes da liberação dos
braços downstream. O artefato publicável
`resultados_publicaveis/estudo_comparativo/avaliacao/VALIDACAO_SETUP.json`
registra `PASS`. IDs de tentativas intermediárias pertencem apenas ao apêndice
técnico; a conclusão canônica é a do Job 90 `2234.HPCGPU`, que terminou com
`Exit_status=0` e validou os resultados em 302 checks sem falhas.

#### Telemetria da referência

As chamadas de Llama e Qwen no job 00 também são medidas. Cada resposta
bem-sucedida acrescenta uma linha a `referencia/_metrics_tokens.jsonl` com:

- modelo;
- stage (`reference_consensus`);
- tokens de prompt, conclusão e total informados pelo endpoint;
- duração HTTP da chamada;
- timestamp e tipo de chamada.

`referencia/_metrics_gpu.csv` amostra utilização, memória e potência da GPU a
cada 15 segundos, e `referencia/_metrics_tempo.csv` mede o tempo de parede da
fase completa. A telemetria por chamada permite agregar tokens e duração
separadamente para Llama e Qwen. O `pass_id` (`a1`, `a2`, `b1`, `b2`) não é
gravado diretamente nessa linha e só pode ser associado pela janela temporal e
pelos checkpoints. A telemetria de GPU é do job/nó e pode ser associada
temporalmente às passagens, mas não é uma medição energética isolada por
modelo.

Esse custo é reportado como custo comum de construção da referência automática.
Ele não entra no desempate entre K-means e LLM, porque todos os braços usam a
mesma referência já congelada. O custo primário da comparação metodológica é o
tempo de parede dos Stages 3–6 de cada braço. Falhas e retries continuam
refletidos no tempo de parede e nas amostras de GPU, ainda que o JSONL de tokens
registre somente respostas HTTP bem-sucedidas.

### 8.2 Job 10 — benchmark da arquitetura legada

**Script:** `../estudo_comparativo/hpc/job_10_m1_legado_llama.sh`.

**Run ID:** `m1_legacy_llama`.

Executa a arquitetura estatística legada mínima:

- Stage 3 por K-means legado;
- Stages 4 a 6 legados;
- Llama nos componentes semânticos;
- mesmo Stage 2 e mesmo alvo curado;
- ambiente comparado ao snapshot do job 00;
- telemetria de tempo, tokens e GPU.

**Interpretação:** comparação descritiva entre arquiteturas completas. Não
isola causalmente K-means, pois vários componentes dos Stages 3 a 6 diferem.

### 8.3 Job 20 — benchmark da arquitetura LLM nativa

**Script:** `../estudo_comparativo/hpc/job_20_m2_nativo.sh`.

**Run ID:** `m2_native`.

Executa:

- Stage 3 hierárquico por LLM;
- Stage 4 vigente;
- Stage 5 vigente;
- validação do Stage 5;
- Stage 6 vigente;
- validação final do portfólio.

Usa Llama para raciocínio, Qwen para JSON e seed 42. Também recebe o mesmo
Stage 2 e o mesmo alvo.

**Interpretação:** segunda arquitetura do benchmark operacional.

### 8.4 Jobs 30 — seis braços da ablação justa

**Script comum:** `../estudo_comparativo/hpc/job_30_ablacao.sh`.

| Run ID | Motor Stage 3 | Seed |
|---|---|---:|
| `kmeans_common_seed42` | BGE-M3 + K-means | 42 |
| `llm_common_seed42` | descoberta hierárquica LLM | 42 |
| `kmeans_common_seed31415` | BGE-M3 + K-means | 31415 |
| `llm_common_seed31415` | descoberta hierárquica LLM | 31415 |
| `kmeans_common_seed27182` | BGE-M3 + K-means | 27182 |
| `llm_common_seed27182` | descoberta hierárquica LLM | 27182 |

Em cada par:

- o Stage 2 é idêntico, inclusive ordem;
- os campos de descoberta são idênticos;
- apenas o motor do Stage 3 muda;
- a saída passa pela mesma interface comum;
- Stages 4, 5 e 6 são os mesmos;
- modelos, hardware, alvo, avaliador e telemetria são congelados.

As três seeds testam sensibilidade a inicialização e ordem de processamento.

**Interpretação:** esta é a comparação apropriada para discutir o efeito do
motor estatístico versus LLM, dentro deste corpus e deste pipeline.

### 8.5 Job 90 — validação, comparação e campos de formulário

**Script:** `../estudo_comparativo/hpc/job_90_avaliacao.sh`.

O job só é liberado se todos os oito braços anteriores terminarem com sucesso.

Ele:

1. verifica novamente o ambiente;
2. exige todos os braços e artefatos;
3. valida identidades de entrada, cobertura e telemetria;
4. audita as informações obrigatórias do portfólio curado;
5. calcula métricas dos métodos;
6. aplica regras pré-registradas;
7. gera relatórios JSON e Markdown;
8. revalida o relatório final;
9. empacota artefatos públicos e privados separadamente.

## 9. Métricas e lógica de conclusão

### 9.1 Estimando

O estimando principal é a aderência retrospectiva, dentro deste corpus, entre a
saída de cada método e o portfólio operacional curado ex post.

Não é uma prova de taxonomia verdadeira nem de generalização futura.

### 9.2 Métrica principal

`macro_best_match_f1_services` compara cada serviço do alvo com seu melhor
grupo correspondente e dá o mesmo peso aos serviços. Assim, categorias de alto
volume não apagam serviços estratégicos menores. O catch-all fica fora dessa
média primária. Como o melhor par é escolhido independentemente para cada
serviço, a análise também publica pareamento húngaro, métricas de partição e
diagnósticos de fusão/fragmentação para não ocultar categorias preditas amplas
demais.

### 9.3 Métricas secundárias

- B-cubed F1;
- Adjusted Rand Index;
- Adjusted Mutual Information;
- taxa mínima de realocação.

Também são analisados:

- tabelas de contingência;
- perdas por serviço;
- request types finais e agrupadores lógicos;
- quatro visões da referência;
- três seeds;
- intervalos bootstrap.

### 9.4 Regra de decisão

- margem material principal: 0,03;
- 2.000 réplicas bootstrap, IC de 95%;
- conclusão forte exige mesma direção nas quatro referências;
- serviços estratégicos precisam de suporte mínimo 5;
- perda máxima tolerada por serviço estratégico: 0,10;
- equivalência exige IC inteiro em `[-0,03, +0,03]`;
- custo só desempata equivalência com diferença mínima de 10%;
- custo, tokens e GPU não são fundidos com qualidade;
- divergência por seed, camada, referência ou métrica gera conclusão sensível
  ou inconclusiva, não um vencedor forçado.

## 10. Por que a métrica não é circular — e qual limitação permanece

A versão antiga era circular quando a própria saída do método ajudava a definir
a “verdade” usada para avaliá-lo.

No desenho final:

- nenhum braço gera sua própria referência;
- a referência é construída antes dos braços;
- todos recebem o mesmo Stage 2;
- a referência projeta demandas diretamente no portfólio curado;
- os métodos são comparados contra as mesmas quatro visões;
- nenhum resultado de braço altera o alvo.

Isso remove a circularidade direta.

A limitação remanescente é **endogeneidade do alvo**: o portfólio curado foi
construído com conhecimento do domínio e apoio das análises do projeto. Portanto,
aderência mede capacidade de reconstruir a decisão adotada, não verdade externa.
O protocolo declara essa limitação e não usa a comparação para “provar” que a
curadoria estava certa.

## 11. Como o projeto responde quais informações o usuário deve fornecer

A resposta combina três fontes:

1. **Stage 2:** extrai `info_fornecidas` e `info_faltantes` dos chamados;
2. **Stage 4:** sugere informações necessárias por grupo natural;
3. **Stage 7:** a gestão congela `informacoes_obrigatorias` por serviço.

O job 90 executa `auditar_campos_portfolio.py`:

- usa BGE-M3 para alinhar evidências textuais do Stage 2 aos campos curados;
- calcula taxas históricas de informação fornecida, faltante e contraditória;
- usa como principal o consenso estrito Llama–Qwen;
- repete o cálculo nas quatro visões da referência;
- reporta faixas de sensibilidade;
- não inventa nem remove campos da decisão gerencial.

Saídas:

- `avaliacao/RESULTADO_CAMPOS_PORTFOLIO.md`;
- `avaliacao/RESULTADO_CAMPOS_PORTFOLIO.metrics.json`.

Esses relatórios justificam empiricamente os formulários, mas a validação final
dos campos continua sendo operacional.

## 12. Artefatos finais e resposta da dissertação

O job 90 deve produzir:

- `avaliacao/VALIDACAO_RESULTS.json`;
- `avaliacao/RESULTADO_COMPARACAO_ROBUSTA.md`;
- `avaliacao/RESULTADO_COMPARACAO_ROBUSTA.metrics.json`;
- `avaliacao/RESULTADO_CAMPOS_PORTFOLIO.md`;
- `avaliacao/RESULTADO_CAMPOS_PORTFOLIO.metrics.json`;
- pacote público sem dados por chamado;
- pacote privado que permanece no HPC.

A conclusão do MBA deve ser organizada em três níveis:

1. **Resultado operacional:** o portfólio curado adotado e seus formulários;
2. **Resultado metodológico:** aderência, robustez e custo dos métodos;
3. **Limitações:** estudo retrospectivo, alvo endógeno, referência automática,
   três seeds e ausência de validação temporal externa.

O avaliador final confirmou a completude dos oito braços, a identidade do
insumo, as réplicas, as camadas de referência e o relatório. A conclusão não é
um vencedor global único; veja `RESULTADOS_COMPARACAO.md`.

## 13. Resultado e histórico de execução

O experimento foi concluído e validado. As medições e a conclusão estão em
`RESULTADOS_COMPARACAO.md`; a linhagem de tentativas, falhas e correções está
isolada em `APENDICE_TECNICO.md`. Essa separação impede que IDs de jobs e
revisões operacionais contaminem a explicação permanente do método.
