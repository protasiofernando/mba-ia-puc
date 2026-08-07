# Triagem Inteligente de Chamados de TI com LLM Local

#### Aluno: [Fernando Nóbrega Mendes Protasio](https://github.com/protasiofernando)
#### Matrícula: 241100336
#### Orientadora: [Manoela Rabello Kohler](https://github.com/manoelakohler)

---

Trabalho apresentado ao curso [BI MASTER](https://ica.puc-rio.ai/bi-master) como pré-requisito para conclusão de curso e obtenção de crédito na disciplina "Projetos de Sistemas Inteligentes de Apoio à Decisão".

- Repositório definitivo:
  [protasiofernando/mba-ia-puc](https://github.com/protasiofernando/mba-ia-puc).

- [Fluxo técnico e metodológico completo do MBA](docs/FLUXO_COMPLETO_MBA.md).

- [Manual formal do projeto](docs/MANUAL_DO_PROJETO.md).

- [Resultados do estudo comparativo](docs/RESULTADOS_COMPARACAO.md).

- [Dashboard estático com os resultados públicos](resultados_publicaveis/RESULTADO_DASHBOARD.html).

- [Documentação técnica e instruções de execução](docs/README_TECNICO.md).

- [Ponto de entrada para IA/auditoria](docs/00_LEIA_PRIMEIRO_IA.md).

- [Auditoria de coerência entre história, scripts e resultados](docs/AUDITORIA_COERENCIA_PROJETO.md).

- [Gate e roteiro para o novo repositório](docs/PUBLICACAO_NOVO_REPOSITORIO.md).

- Este `README.md` funciona como síntese acadêmica do trabalho; os documentos
  vinculados preservam o detalhamento metodológico, os resultados e a auditoria.

---

> **Estado final em 07/08/2026.** O estudo foi concluído no A100 sobre 1.456
> chamados. O Job 90 terminou com `Exit_status=0` e a validação passou em 302
> checks, sem falhas. A evidência primária favorece K-means, especialmente em
> custo, mas a aderência varia por semente, camada e referência; portanto, não
> há vencedor global único. O portfólio curado permanece a decisão operacional.
> Depois do estudo, o Stage 7 projetou automaticamente os 1.456 chamados nesse
> portfólio; o agregado publicável está em `pipeline_data/07_portfolio_final.json`.
> Veja [`docs/RESULTADOS_COMPARACAO.md`](docs/RESULTADOS_COMPARACAO.md).

> Este repositório reúne duas contribuições. A **aplicada** é o redesenho do
> portfólio da DTI Pesquisa, com dashboard e curadoria estratégica. A
> **metodológica** é uma comparação entre descoberta estatística
> (`bge-m3` + K-means) e descoberta hierárquica por LLM. O desenho separa um
> benchmark descritivo das arquiteturas completas de uma ablação realmente
> controlada do Stage 3, com três seeds, referência automática Llama+Qwen,
> métricas por serviço, custo separado e regra de decisão pré-registrada.
> Comece pelo
> **[dossiê de auditoria](estudo_comparativo/DOSSIE_AUDITORIA.md)**.

### Arquitetura vigente

O repositório está organizado em três fases, que não devem ser misturadas:

1. **Formação:** o Método Estatístico produz um candidato automático nos
   Stages 3–6; a implementação e a linhagem ficam em `formacao_portfolio/`.
2. **Curadoria:** a área revisa o candidato no nível do catálogo e congela a
   decisão em `formacao_portfolio/decisao_curada/feedback_portfolio.json`; não
   rotula chamados manualmente. O Stage 7 possui materializador, classificador
   automático e job PBS; sua projeção operacional posterior ao estudo foi
   concluída sobre os 1.456 chamados.
3. **Comparação:** depois do congelamento, os métodos Estatístico e Agêntico
   são reexecutados sobre o mesmo Stage 2 de 1.456 chamados para medir
   aderência, estabilidade e custo. O ZIP é code-only.

Componentes principais:

| Caminho | Papel |
|---|---|
| `scripts/` | Stages, validadores, avaliador e geradores de pacote |
| `dashboard/` | Aplicação Flask local |
| `configuracao/` | Identidade, contexto institucional e catálogo real |
| `data/` | CSVs reais sensíveis, fora do Git |
| `pipeline_data/` | Artefatos agregados versionáveis e saídas locais permitidas |
| `formacao_portfolio/` | Snapshot imutável, formação e decisão curada congelada |
| `estudo_comparativo/` | Protocolo, regras, jobs PBS e runbook do estudo |
| `resultados_publicaveis/` | Relatórios, métricas e gates agregados do Job 90 |
| `docs/` | Narrativa, resultado, estado e apêndice técnico |
| `metodo_estatistico/` | Motor estatístico mantido, usado na formação e reexecutado na comparação |

Para outra IA retomar o projeto, o caminho mais barato e
[`docs/00_LEIA_PRIMEIRO_IA.md`](docs/00_LEIA_PRIMEIRO_IA.md) ->
[`docs/ESTADO_COMPARACAO_ROBUSTA.json`](docs/ESTADO_COMPARACAO_ROBUSTA.json).

### Resumo

As áreas de suporte de TI organizam seus atendimentos em catálogos de serviços definidos, na maioria das vezes, pela intuição dos gestores — e não pela análise sistemática do que os usuários realmente solicitam. Este trabalho apresenta um sistema de apoio à decisão que reavalia o portfólio de serviços de tecnologia para pesquisa da Diretoria de Tecnologia da Informação (DTI) da Fundação Getulio Vargas (FGV) a partir do histórico real de chamados. Um pipeline executado integralmente na infraestrutura de HPC da instituição usa modelos de linguagem locais (`llama3.3:70b` para raciocínio e `qwen3:30b-a3b-instruct-2507-q4_K_M` para saída estruturada, via Ollama em GPU NVIDIA A100) para destilar intenções, descobrir grupos de demanda, recomendar um catálogo e reclassificar o histórico. Como contribuição metodológica, a descoberta foi comparada por duas abordagens — embeddings `bge-m3` + K-means e descoberta hierárquica por LLM — numa ablação comum com três seeds e referência automática Llama+Qwen. A evidência primária favoreceu K-means e o custo estatístico, mas não sustentou vencedor global único por sensibilidade à semente, camada e referência. O resultado operacional é um portfólio curado de sete serviços, um catch-all e Sala de Sigilo como encaminhamento fixo, com escopo e campos obrigatórios definidos. Nenhum dado histórico sensível deixa a infraestrutura institucional.

**Palavras-chave:** gestão de serviços de TI; mineração de chamados; modelos de
linguagem; agrupamento; apoio à decisão; catálogo de serviços.

### Abstract

IT support areas often organize service catalogs through managerial intuition rather than systematic analysis of user demand. This work presents a decision-support system that redesigns the research-technology portfolio of Fundação Getulio Vargas from historical support tickets. Locally hosted models on the institutional HPC distill intent, discover demand groups, recommend a catalog and reclassify the history. As a methodological contribution, `bge-m3` embeddings plus K-means were compared with hierarchical LLM discovery under a common downstream pipeline, three seeds and an automatic Llama+Qwen reference. Primary evidence favored K-means and the statistical cost profile, but did not support a unique global winner because results varied by seed, evaluation layer and reference view. The operational outcome is a curated seven-service portfolio, a catch-all and the secure-room service as a fixed referral, with defined scope and required fields. Historical sensitive data never leaves the institutional infrastructure.

**Keywords:** IT service management; ticket mining; large language models;
clustering; decision support; service catalog.

### 1. Introdução

#### 1.1 Contexto e problema

A DTI da FGV atende, pelo seu portal de serviços, as demandas de tecnologia dos professores e pesquisadores da instituição: acesso a servidores acadêmicos, computação em nuvem, HPC, máquinas virtuais, softwares científicos e armazenamento de dados de pesquisa. Esses atendimentos são registrados como chamados no Jira e classificados em um catálogo de 18 categorias que foi construído incrementalmente, com base na percepção dos gestores sobre a demanda.

A gestão sistemática desses serviços envolve planejar, desenhar, entregar,
medir e melhorar os serviços para produzir valor, conforme o escopo da
ISO/IEC 20000-1 (ISO; IEC, 2018). Em centrais de atendimento, a classificação
correta já na abertura também é relevante para encaminhar a solicitação à área
responsável e evitar atrasos associados a reclassificações sucessivas
(AL-HAWARI; BARHAM, 2021). Nesse contexto, o catálogo não é apenas uma lista de
opções: ele funciona como interface entre a necessidade do usuário, a coleta de
informações e a operação que prestará o serviço.

Três evidências indicavam que esse catálogo não refletia mais a realidade. Primeiro, a opção genérica "Não encontrou o que procurava?" era a terceira categoria mais acionada na base completa (203 de 1.584; 12,8%), sinal de que os usuários não localizavam onde abrir seus pedidos. Segundo, havia categorias sobrepostas disputando o mesmo tipo de solicitação. Terceiro — e mais custoso — chamados abertos sem as informações necessárias geravam idas e vindas de esclarecimento: no universo analítico, chamados que exigiram múltiplas interações levaram, em média, 5,22 vezes mais tempo para serem resolvidos do que os atendidos de forma direta; na base completa pré-filtro, a razão era 5,51 (seção 4.3).

A dificuldade desse tipo de reavaliação é que o insumo relevante — o texto livre de milhares de chamados, com títulos vagos, descrições incompletas e comentários de acompanhamento — pode ser representado de maneiras lexicalmente diferentes para uma mesma intenção. Modelos de sentença baseados em Transformers foram propostos justamente para produzir representações semânticas comparáveis e úteis em busca e agrupamento (REIMERS; GUREVYCH, 2019). O uso de LLMs e embeddings amplia essa capacidade, mas APIs externas esbarram em uma restrição institucional: os chamados contêm dados pessoais e não podem deixar a infraestrutura da FGV.

#### 1.2 Questão de pesquisa e objetivos

A questão central é: **como um pipeline de inteligência artificial executado
localmente pode apoiar, de forma auditável, o redesenho de um catálogo de
serviços de TI a partir de chamados históricos?** A contribuição metodológica
desdobra uma segunda questão: **sob o mesmo insumo e a mesma camada semântica
posterior, como a descoberta por embeddings `bge-m3` + K-means e a descoberta
hierárquica por LLM se comparam em aderência, robustez e custo?** A investigação
não pressupõe superioridade de um método e admite como resultado válido um
trade-off ou uma conclusão sensível à camada.

Este trabalho explora a viabilidade de um caminho intermediário: executar LLMs abertos localmente na infraestrutura de HPC já existente na instituição, combinando três famílias de técnicas — sumarização estruturada por LLM, descoberta de grupos naturais de demanda (por embeddings ou por LLM) e classificação assistida por LLM — em um pipeline offline cujo resultado alimenta um sistema interativo de apoio à decisão.

O objetivo geral é redesenhar o portfólio de serviços com base em evidências, e os objetivos específicos são: (i) extrair a intenção real de cada chamado histórico, independentemente da categoria em que foi aberto; (ii) descobrir os grupos naturais de demanda sem partir das categorias existentes; (iii) diagnosticar sobreposições, lacunas e fragmentações do catálogo vigente; (iv) propor e consolidar, com curadoria humana, um portfólio otimizado com escopo, campos obrigatórios e SLA por categoria; e (v) disponibilizar um assistente de triagem que classifique novos chamados nesse portfólio em tempo real, antecipando as informações necessárias.

### 2. Fundamentação teórica

#### 2.1 Gestão de serviços e classificação de chamados

A ISO/IEC 20000-1 situa planejamento, desenho, transição, entrega, medição e
melhoria contínua dentro de um sistema de gestão de serviços (ISO; IEC, 2018).
Para este projeto, essa perspectiva fundamenta duas escolhas: tratar o catálogo
como artefato de gestão, e não apenas como taxonomia textual, e preservar na
decisão final critérios de responsabilidade, governança e valor operacional.

No domínio de *help desk*, Al-Hawari e Barham (2021) mostram que a classificação
automática de chamados pode apoiar a escolha do serviço correto desde a
abertura, reduzindo encaminhamentos inadequados. O presente trabalho parte do
mesmo problema operacional, mas amplia o escopo: antes de classificar novos
chamados, reavalia se as próprias categorias oferecidas correspondem à demanda
histórica. Assim, descoberta de grupos, desenho do catálogo e triagem formam
etapas relacionadas, porém distintas.

#### 2.2 Representações semânticas e descoberta de grupos

Embeddings de sentenças permitem comparar textos pelo conteúdo semântico, em
vez de depender apenas da coincidência de termos (REIMERS; GUREVYCH, 2019). O
`bge-m3`, utilizado no método estatístico, oferece representação multilíngue e
suporte a diferentes granularidades textuais (CHEN et al., 2024). Essa base
justifica representar as intenções destiladas no Stage 2 como vetores e aplicar
K-means, algoritmo particional que busca minimizar a dispersão interna dos
grupos em torno de centroides (MACQUEEN, 1967).

Não existe, contudo, um número de grupos naturalmente garantido. A silhueta
avalia simultaneamente coesão interna e separação entre grupos (ROUSSEEUW,
1987), mas responde à geometria da representação e não determina, sozinha, a
utilidade de negócio do catálogo. Por isso, o projeto separa a descoberta
estatística do julgamento sobre escopo, governança e navegabilidade.

#### 2.3 Avaliação, robustez e decisão humano–IA

A comparação entre partições requer métricas corrigidas para concordância ao
acaso, como o índice de Rand ajustado (HUBERT; ARABIE, 1985), e medidas
informacionais normalizadas ou ajustadas (VINH; EPPS; BAILEY, 2010). Além da
aderência a uma referência, a estabilidade entre reexecuções é relevante para
distinguir estrutura persistente de variação induzida por amostragem ou
inicialização (LANGE et al., 2004). Essa literatura sustenta o uso conjunto de
Macro-F1 por serviço, B-cubed, ARI, AMI, reatribuição entre seeds e análise de
custo, sem condensá-los em uma nota composta arbitrária.

O projeto também se enquadra em *design science*: constrói e avalia artefatos
tecnológicos destinados a ampliar capacidades organizacionais (HEVNER et al.,
2004). A curadoria no nível do catálogo preserva decisão e responsabilidade
humanas, enquanto a IA oferece evidências, alternativas e projeções. Essa
separação é coerente com recomendações de interação humano–IA que enfatizam
explicitar capacidades, permitir correção e apoiar o usuário quando o sistema
estiver incerto (AMERSHI et al., 2019).

### 3. Modelagem

#### 3.1 Delineamento da pesquisa

Trata-se de uma pesquisa aplicada, com construção e avaliação de artefatos sob
a perspectiva de *design science*. A unidade de análise é o chamado individual;
os artefatos produzidos são o pipeline auditável, o candidato automático de
portfólio, a decisão curada, a classificação operacional e o dashboard. O
universo temporal e organizacional restringe-se aos chamados da DTI Pesquisa
da FGV entre 2024 e 2026.

A avaliação possui dois estimandos deliberadamente separados: o benchmark das
arquiteturas completas e a ablação controlada do motor de descoberta no Stage
3. A comparação usa o mesmo Stage 2 congelado, a mesma interface e os mesmos
Stages 4–6; três seeds observam sensibilidade à inicialização. A referência por
chamado é automática, por consenso Llama+Qwen, e mede aderência ao portfólio
curado, não acurácia contra uma verdade externa. Custo, aderência e estabilidade
são reportados separadamente. O protocolo e as regras de decisão foram
registrados antes da avaliação final em
[`estudo_comparativo/PROTOCOLO_METODOLOGICO.md`](estudo_comparativo/PROTOCOLO_METODOLOGICO.md).

#### 3.2 Dados

A base original reúne os chamados do portal de serviços de pesquisa registrados entre 2024 e 2026 — **1.584 chamados** após deduplicação. Para a comparação, uma regra exata sobre `Customer Request Type` removeu 128 registros antes do Stage 1, restando **1.456 chamados**. Todos os 128 registros efetivamente removidos tinham o rótulo legado **“Solicitação de Acesso a Bases de Dados”**, pertencente ao fluxo de dados confidenciais/Sala de Sigilo e atendido fora da DTI Pesquisa pela equipe de Banco de Dados; os outros seis rótulos da lista de exclusão tiveram zero ocorrências no período. Esse item legado não é o serviço homônimo do portfólio curado: o serviço final atende acesso comum a pastas e bases de pesquisa **fora da Sala de Sigilo** e substitui “Acessar pastas de dados de pesquisa”. A distinção institucional e as contagens estão em [`configuracao/contexto_catalogo.md`](configuracao/contexto_catalogo.md), e a decisão curada a registra em [`feedback_portfolio.json`](formacao_portfolio/decisao_curada/feedback_portfolio.json). Cada chamado traz título, descrição, categoria atribuída, situação, datas, responsáveis e comentários. Os dados brutos contêm dados pessoais e **não são versionados**. O script `scripts/gerar_base_sintetica.py` produz localmente em `data_exemplo/` uma amostra inteiramente artificial com o mesmo schema para demonstração, usando apenas o catálogo agregado público; por política de publicação, nenhum CSV integra este repositório. **Todos os números aplicados apresentados neste trabalho foram calculados sobre a base real, dentro da infraestrutura da FGV**.

#### 3.3 Arquitetura em três camadas

O sistema separa o processamento pesado, executado uma única vez, do uso interativo:

1. **Pipeline offline (HPC)** — Stages 1–6 executados no nó GPU (NVIDIA A100) via PBS, com os LLMs `llama3.3:70b` (raciocínio) e `qwen3:30b` (compilação de JSON) e o modelo de embeddings `bge-m3` servidos localmente pelo Ollama. O Stage 7 é a curadoria gerencial posterior. O fluxo consome os CSVs do Jira e persiste os resultados como JSON.
2. **Simulação de triagem** — classificação de novos chamados em tempo real, via LLM local (túnel SSH até o nó GPU) ou Azure OpenAI (opcional; recebe apenas o texto digitado na simulação, nunca dados históricos).
3. **Dashboard web (Flask + SQLite + Chart.js)** — quatro abas: Tipos de Chamado Sugeridos, Indicadores, Prévia do Portal e Histórico.

#### 3.4 Pipeline de sete estágios

| Stage | Técnica | O que faz |
|-------|---------|-----------|
| 1 — Extração | regras | Lê os CSVs do Jira, limpa HTML/URLs/e-mails e estrutura os campos relevantes |
| 2 — Sumarização | LLM | Para cada chamado, destila um resumo estruturado: `intencao`, `tema`, `tipo_pedido`, `contexto`, campos fornecidos/faltantes e a tag `descricao_insuficiente` (se o atendente precisou pedir informações) |
| 3 — Descoberta de grupos | `bge-m3` + K-means ou LLM hierárquica | A formação inicial usou o motor estatístico; o segundo método usa descoberta por LLM; a comparação reexecuta os dois sob interface comum |
| 4 — Rotulação | LLM | Nomeia cada grupo e define descrição, critério de uso, campos obrigatórios e SLA |
| 5 — Comparação | LLM | Compara o catálogo vigente (com volumes reais) com os grupos naturais e gera o diagnóstico e o portfólio otimizado recomendado |
| 6 — Classificação | LLM | Reclassifica cada chamado histórico no portfólio recomendado, com justificativa e confiança |
| 7 — Finalização curada | curadoria humana + projeção automática | Congela a decisão em `formacao_portfolio/decisao_curada/feedback_portfolio.json`; `materializar_portfolio_curado.py` cria o agregado e `run_stage7_curadoria.py` classifica os chamados sem rótulos manuais |

O princípio central da modelagem: **o LLM entende e destila cada chamado
(Stage 2) → a descoberta agrupa os pedidos pela intenção (Stage 3, por
estatística ou por LLM) → os Stages 4–6 transformam os grupos em proposta e
evidência operacional → a curadoria humana consolida o portfólio → o Stage 7
opcional projeta automaticamente os chamados no catálogo congelado**. O fluxo
detalhado, incluindo a diferença entre stage e job, está em
[`docs/FLUXO_COMPLETO_MBA.md`](docs/FLUXO_COMPLETO_MBA.md). Nenhum estágio usa
TF-IDF ou contagem de termos: as keywords dos grupos são os campos `tema`
gerados pelo LLM.

Duas decisões de projeto merecem destaque. A primeira é a separação entre recomendação e decisão: o Stage 5 produz um candidato, enquanto as categorias finais, diretrizes e encaminhamentos vivem em `formacao_portfolio/decisao_curada/`. O materializador valida deterministicamente que `portfolio_referencia.json` é o espelho analítico de `feedback_portfolio.json`; a projeção por chamado do Stage 7 continua automática. A segunda é a resiliência operacional: sumarização e classificações usam checkpoints vinculados ao conteúdo, e todas as chamadas ao LLM passam por retry e validação de JSON.

#### 3.5 Infraestrutura e privacidade

Todo o processamento dos dados históricos ocorre dentro da infraestrutura da FGV: os modelos rodam no nó GPU do HPC institucional (NVIDIA A100), servidos pelo Ollama. A escolha de modelos abertos — `llama3.3:70b` para as tarefas de raciocínio e `qwen3:30b-a3b-instruct-2507-q4_K_M` para compilar a saída estruturada em JSON — equilibra qualidade de instrução em português e viabilidade de execução local. Os arquivos com texto ou classificação por chamado são mantidos fora do versionamento; apenas agregados são versionados. Detalhes operacionais estão em [docs/MANUAL_HPC.md](docs/MANUAL_HPC.md).

### 4. Resultados e discussão

#### 4.1 Diagnóstico do portfólio vigente

Os números de grupos pertencem a etapas distintas e não devem ser confundidos: o snapshot histórico que iniciou a formação do portfólio tinha **23 grupos**, enquanto a execução comparativa final produziu **29 clusters** no método estatístico e **20 tipos de requisição** no método agêntico, antes da consolidação semântica. Em contraste com as 18 categorias do catálogo vigente, as três leituras evidenciaram categorias amplas demais, demandas recorrentes sem categoria própria e fragmentação de pedidos semelhantes. Na base completa de 1.584 chamados, o item “Não encontrou o que procurava?” reunia 203 casos (12,8%) e era a terceira categoria mais usada; esse percentual é um diagnóstico pré-filtro, não a distribuição do universo comparativo de 1.456.

#### 4.2 Portfólio final

Após a revisão da recomendação automática pela área, o portfólio final curado
organiza a demanda em **7 serviços**, um *catch-all* e o encaminhamento fixo
*Sala de Sigilo*:

| Grupo | Categoria final | Papel no catálogo |
|---|---|---|
| Infraestrutura Computacional | Servidores Acadêmicos Compartilhados | serviço analítico |
| Infraestrutura Computacional | HPC e Processamento de Alto Desempenho (GPU) | serviço analítico estratégico |
| Infraestrutura Computacional | Máquinas Virtuais Individuais (Portal do Pesquisador) | serviço analítico estratégico |
| Softwares e Licenças | Softwares e Licenças Acadêmicas | serviço analítico |
| Nuvem Pública | Nuvem Pública (AWS, Azure, GCP) | serviço analítico |
| Dados e Governança de Pesquisa | Submissão do Plano de Gestão de Dados (PGD) de Pesquisa | serviço analítico estratégico |
| Dados e Governança de Pesquisa | Solicitação de Acesso a Bases de Dados | serviço analítico |
| Triagem | Não encontrou o que procurava? | *catch-all* residual |
| Encaminhamentos | Sala de Sigilo | visível, imutável e fora da análise |

Cada categoria carrega um critério de uso (`quando_usar`), a lista de
informações obrigatórias a coletar na abertura e o SLA sugerido — insumos
diretos para o novo formulário do portal e para o assistente de triagem. O
Stage 7 vigente foi materializado automaticamente depois do encerramento do
estudo. A projeção operacional, que não altera as métricas comparativas, foi:

| Categoria analítica | Chamados | Participação |
|---|---:|---:|
| Servidores Acadêmicos Compartilhados | 455 | 31,2% |
| Nuvem Pública (AWS, Azure, GCP) | 426 | 29,3% |
| Softwares e Licenças Acadêmicas | 246 | 16,9% |
| Máquinas Virtuais Individuais | 98 | 6,7% |
| HPC e Processamento de Alto Desempenho | 95 | 6,5% |
| Solicitação de Acesso a Bases de Dados | 65 | 4,5% |
| Submissão do Plano de Gestão de Dados | 48 | 3,3% |
| Não encontrou o que procurava? | 23 | 1,6% |

Os volumes somam os 1.456 chamados do universo analítico e não incluem Sala de
Sigilo. São uma classificação automática retrospectiva no catálogo curado, não
uma medição de adoção do novo portal nem evidência causal de redução do item
residual. O agregado versionável está em `pipeline_data/07_portfolio_final.json`;
a classificação por chamado permanece privada e ignorada pelo Git.

#### 4.3 Associação entre interações e tempo de resolução

A evidência que motiva a triagem assistida é a associação observada entre
múltiplas interações e maior tempo de resolução. O cálculo, implementado em
[`scripts/analise_tempo_interacoes.py`](scripts/analise_tempo_interacoes.py), é
definido assim:

- **Interação humana**: comentário do chamado cujo autor não é o robô de automação do Jira (autor ≠ `automato`);
- **Resolução direta**: chamado resolvido com **até 1** interação humana;
- **Múltiplas interações**: chamado que exigiu **2 ou mais** trocas com o solicitante;
- **Tempo de resolução**: diferença entre as datas de resolução e criação, em dias; consideram-se apenas chamados com tempo válido (resolução posterior à criação);
- **Razão descritiva** = tempo(múltiplas) / tempo(direta).

Como o diagnóstico operacional foi calculado antes da definição do recorte
comparativo, há dois denominadores legítimos. Eles são declarados separadamente:

| Universo | Tempo válido | Direta (n; média; mediana) | Múltiplas (n; média; mediana) | Razão das médias | Razão das medianas |
|---|---:|---|---|---:|---:|
| Base completa pré-filtro | 1.561 | 333; 2,5 dias; 0,4 dia | 1.228; 13,9 dias; 5,7 dias | 5,51x | 14,75x |
| Universo analítico pós-filtro | 1.440 | 329; 2,6 dias; 0,4 dia | 1.111; 13,4 dias; 5,8 dias | 5,22x | 14,01x |

No ambiente interno, o comando sem argumentos lê o diretório privado `data/`,
que contém o universo analítico de 1.456 registros, e portanto reproduz
**5,22x**. O valor **5,51x** requer a cópia privada pré-filtro de 1.584
registros, informada com `--dados`;
essa base não pode ser publicada. Os valores descrevem os grupos históricos e
não estimam quanto tempo seria economizado ao alterar o formulário.

Como os dados reais do Jira não são publicados, `scripts/gerar_base_sintetica.py`
pode gerar em `data_exemplo/` uma amostra inteiramente artificial para
demonstrar o cálculo. O gerador lê somente o portfólio agregado público e cria
textos, pessoas, datas, durações e interações fictícios; não acessa Stage 1,
Stage 2 ou qualquer distribuição por chamado. O CSV gerado localmente permanece
ignorado pelo Git.

Depois de gerar a base sintética:

```bash
python scripts/gerar_base_sintetica.py
python scripts/analise_tempo_interacoes.py --dados data_exemplo
```

Os números sintéticos servem somente para verificar a execução.

**Ressalva metodológica**: trata-se de uma associação, não de uma relação causal
isolada — chamados intrinsecamente mais complexos tendem tanto a exigir mais
interações quanto a demorar mais. Uma análise complementar com a tag
`descricao_insuficiente` mostra a mesma direção, com magnitude menor: 1,9x na
média. Essas análises motivam a coleta de campos, mas não quantificam um ganho
causal atribuível ao novo formulário.

#### 4.4 Assistente de triagem

Com o portfólio final como contexto, o assistente classifica um chamado novo em tempo real: recebe título e descrição, devolve a categoria sugerida, a justificativa e as informações que faltam para o atendimento direto. No dashboard, a simulação funciona com o LLM local (mesmo modelo do pipeline) ou, opcionalmente, com Azure OpenAI — caso em que apenas o texto digitado é enviado, nunca dados históricos.

#### 4.5 Reprodutibilidade e demonstração

Qualquer pessoa que clone este repositório consegue executar o painel localmente:

```bash
pip install -r requirements.txt
python dashboard/app.py   # http://localhost:5000
```

- A aba **Tipos de Chamado Sugeridos** abre pronta, exibindo os resultados agregados **reais** do pipeline (JSONs versionados em `pipeline_data/`, sem dados pessoais): diagnóstico executivo, portfólio curado, projeção agregada do Stage 7 e consolidação do catálogo.
- As abas **Indicadores** e **Histórico** dependem de `dashboard/runtime/knowledge_base.db`. Qualquer pessoa pode gerar a base artificial com `python scripts/gerar_base_sintetica.py` e, depois, usar `$env:JIRA_DATA_DIR="data_exemplo"; python scripts/knowledge_base.py`. Esses indicadores são demonstrativos; os resultados oficiais são os agregados versionados.
- A aba **Prévia do Portal** mostra o catálogo proposto; a simulação ao vivo exige credenciais Azure OpenAI em `.env`.
- A associação entre tempo e interações (seção 4.3) pode rodar sobre a base
  sintética depois que ela for gerada; é observacional e não deve ser
  interpretada como efeito causal.
- **Comparação dos dois métodos:** desenho, status, linhagem e execução em
  [estudo_comparativo/DOSSIE_AUDITORIA.md](estudo_comparativo/DOSSIE_AUDITORIA.md).

As instruções completas de instalação e execução estão em [docs/README_TECNICO.md](docs/README_TECNICO.md).

#### 4.6 Comparação robusta dos métodos de descoberta

A comparação parte de um Stage 2 congelado com 1.456 chamados, produzido depois
da remoção determinística dos 128 registros do request type legado homônimo
“Solicitação de Acesso a Bases de Dados”, pertencente ao fluxo de dados
confidenciais/Sala de Sigilo e atendido fora da DTI Pesquisa pela equipe de
Banco de Dados. O serviço final de acesso comum a bases é outro objeto
operacional e permanece no catálogo curado. Nenhuma LLM ou texto
livre decide o escopo.

Há dois resultados separados:

1. um benchmark descritivo das arquiteturas completas;
2. uma ablação do Stage 3 em que K-means e LLM usam o mesmo insumo, os mesmos
   campos, a mesma interface canônica e os mesmos Stages 4–6.

A ablação tem três pares de seeds e é confrontada com o portfólio curado por uma
referência automática Llama+Qwen em quatro visões. A métrica principal dá o
mesmo peso aos serviços; ARI e outras métricas são secundárias. A regra pode
concluir superioridade, equivalência, trade-off ou resultado sensível, sem nota
composta.

O target é o portfólio operacional adotado, não uma verdade externa. Assim, a
comparação mede aderência à decisão da área e explicita a endogeneidade da
curadoria. O custo dos Stages 3–6 é medido separadamente.

**Resultado:** a validação final passou em 302 checks, sem falhas. A evidência
primária favorece K-means e o custo estatístico, mas benchmark e ablação foram
classificados como dependentes da camada. Portanto, não há vencedor global
único de aderência. A linhagem de tentativas invalidadas está em
[`docs/APENDICE_TECNICO.md`](docs/APENDICE_TECNICO.md), e as tabelas completas
estão em [`docs/RESULTADOS_COMPARACAO.md`](docs/RESULTADOS_COMPARACAO.md).

#### 4.7 Discussão integrada

Os resultados respondem afirmativamente à questão aplicada: foi possível
transformar chamados históricos em evidência auditável para redesenhar o
catálogo sem transferir dados sensíveis para serviços externos. A descoberta
não decidiu sozinha o portfólio. Ela revelou padrões de demanda; a área
converteu esses padrões em serviços com responsabilidade, escopo e campos de
abertura; e o Stage 7 projetou automaticamente o histórico na decisão
congelada. Essa sequência materializa o princípio de *design science* de avaliar
um artefato pela relação entre problema organizacional, construção e utilidade
(HEVNER et al., 2004).

O diagnóstico de categorias sobrepostas e do uso elevado do item genérico é
coerente com a literatura de classificação de chamados: uma taxonomia ambígua
pode prejudicar o encaminhamento correto já na abertura (AL-HAWARI; BARHAM,
2021). A projeção de apenas 1,6% do histórico analítico no *catch-all* mostra que
o catálogo curado oferece cobertura retrospectiva mais específica. Esse número,
entretanto, não prova que usuários futuros escolherão corretamente os novos
itens; essa hipótese exige acompanhamento após a implantação.

Quanto à questão metodológica, K-means recebeu o sinal mais favorável na
evidência primária e apresentou menor custo, mas sua vantagem não permaneceu
invariante entre sementes, camadas e referências. A conclusão é compatível com
a literatura de validação de agrupamentos: coesão, concordância externa e
estabilidade medem propriedades diferentes e não devem ser substituídas por um
único indicador (ROUSSEEUW, 1987; LANGE et al., 2004; VINH; EPPS; BAILEY,
2010). Portanto, o achado não é que um algoritmo seja universalmente superior,
mas que o motor estatístico oferece o melhor compromisso observado na evidência
primária e no custo deste domínio.

A associação de 5,22 vezes no universo analítico — e de 5,51 vezes na base
completa pré-filtro — entre as médias dos grupos com múltiplas interações e
resolução direta reforça a utilidade operacional de coletar campos obrigatórios.
Ainda assim, complexidade do chamado, prioridade e disponibilidade da equipe
podem afetar simultaneamente interações e duração. O projeto usa esse resultado
para motivar o desenho do formulário, não para prometer redução causal de tempo.

Por fim, manter a curadoria humana e tornar visíveis justificativa, confiança e
informações faltantes evita tratar a IA como decisora autônoma. A arquitetura
apoia revisão e correção, em linha com as recomendações de interação humano–IA
de Amershi et al. (2019).

#### 4.8 Ameaças à validade

- **Validade de construto:** o portfólio curado é uma decisão operacional da
  própria área, não uma *ground truth* externa. A referência Llama+Qwen reduz a
  dependência de um único modelo, mas continua automática. Estudos sobre
  LLMs avaliadores mostram que julgamentos podem sofrer vieses sistemáticos
  (SHI et al., 2025); por isso, o trabalho interpreta as métricas como aderência
  ao alvo adotado, e não como acurácia absoluta.
- **Validade interna:** as três seeds e a camada comum dos Stages 4–6 controlam
  parte da variabilidade, mas não eliminam a não determinação dos modelos. A
  análise de interações e tempo é observacional e não controla todos os fatores
  de complexidade; nenhuma conclusão causal é formulada.
- **Validade externa:** os dados pertencem a uma única área de serviços de TI,
  em uma instituição e janela temporal específicas. A arquitetura é
  transferível, mas os serviços descobertos, limiares e custos não devem ser
  generalizados sem nova execução e validação local.
- **Validade de conclusão:** Macro-F1, B-cubed, ARI, AMI, reatribuição e custo
  reduzem a dependência de uma única métrica; três seeds, porém, não cobrem toda
  a variabilidade possível. A conclusão conservadora — ausência de vencedor
  global único — respeita essa limitação.
- **Reprodutibilidade e privacidade:** código, configurações, hashes, resultados
  agregados e 302 checks são públicos. Textos e classificações por chamado não
  podem ser divulgados, o que limita a reprodução independente dos números
  exatos, mas preserva a obrigação institucional de proteção dos dados.
- **Auditabilidade temporal:** o repositório público foi consolidado depois da
  execução e publicou regras e resultados no mesmo commit-raiz. Assim, seu
  histórico Git não comprova de forma independente a anterioridade temporal do
  pré-registro. Manifestos, hashes, timestamps de jobs e o apêndice técnico
  preservam a proveniência interna, mas não equivalem a um carimbo de tempo de
  terceiro. Uma replicação futura deve registrar protocolo e regras em serviço
  externo imutável antes de liberar os resultados.

### 5. Conclusões

O trabalho demonstrou que é viável — técnica e institucionalmente — usar LLMs para redesenhar um portfólio de serviços a partir da demanda real, sem que nenhum dado sensível deixe a infraestrutura da organização. Quatro conclusões se destacam:

1. **Dados qualificam a decisão gerencial no desenho de catálogos.** O portfólio vigente, construído incrementalmente pela percepção dos gestores, divergia de forma mensurável da estrutura encontrada nos chamados: o snapshot de formação tinha 23 grupos, e a comparação final encontrou 29 clusters estatísticos e 20 tipos agênticos, frente a 18 categorias vigentes. O portfólio final transforma essa evidência em sete serviços com escopos mais claros, um *catch-all* residual e Sala de Sigilo como encaminhamento fixo. A projeção automática posterior do Stage 7 atribuiu 1,6% do histórico analítico ao *catch-all*; a participação futura em produção ainda deve ser medida após a implantação.
2. **LLMs abertos locais dão conta da tarefa.** Os modelos `llama3.3:70b` (raciocínio) e `qwen3:30b` (compilação de JSON), rodando em GPU A100, sustentaram todas as etapas semânticas do pipeline (sumarização, rotulação, diagnóstico e classificação) com saída estruturada confiável — ao custo de um processamento offline de poucas horas, adequado para uma análise que se repete apenas periodicamente.
3. **A curadoria humana é parte do método, não um ajuste posterior.** A separação entre recomendação automática e decisão de negócio (`formacao_portfolio/decisao_curada/feedback_portfolio.json`) tornou o resultado adotável. A área preserva serviços por responsabilidade, governança e visibilidade, inclusive quando o volume é baixo. Sala de Sigilo é um encaminhamento fixo e não participa da comparação.
4. **A comparação metodológica precisa separar aderência, robustez e custo.** O protocolo não escolhe um vencedor por uma única métrica: confronta serviços, seeds, referências e camadas e mede custo separadamente. A evidência primária favorece K-means, mas a sensibilidade à camada impede declarar vencedor global único.

As principais limitações apontam os trabalhos futuros: o método estatístico impõe grupos disjuntos e depende de um K sem valor natural (silhueta sensível à composição da base), enquanto o agêntico é caro em tokens; a análise de ganho de tempo mede associação, não causalidade — o desenho ideal seria comparar coortes antes/depois da adoção do novo portal; e a validação cobre um único domínio (serviços de tecnologia para pesquisa). Os próximos passos naturais são medir a adoção em produção (evolução do uso do item genérico e da taxa de resolução direta), reexecutar o pipeline periodicamente para detectar deriva da demanda e replicar o método em outras áreas de atendimento da instituição — o que o desenho genérico do pipeline já permite sem alteração de código.

### 6. Referências

AL-HAWARI, F.; BARHAM, H. A machine learning based help desk system for IT
service management. *Journal of King Saud University – Computer and Information
Sciences*, v. 33, n. 6, p. 702–718, 2021.
[https://doi.org/10.1016/j.jksuci.2019.04.001](https://doi.org/10.1016/j.jksuci.2019.04.001).

AMERSHI, S. et al. Guidelines for human-AI interaction. In: *CHI Conference on
Human Factors in Computing Systems Proceedings*. New York: ACM, 2019. p. 1–13.
[https://doi.org/10.1145/3290605.3300233](https://doi.org/10.1145/3290605.3300233).

CHEN, J. et al. M3-Embedding: multi-linguality, multi-functionality,
multi-granularity text embeddings through self-knowledge distillation. In:
*Findings of the Association for Computational Linguistics: ACL 2024*.
Bangkok: Association for Computational Linguistics, 2024. p. 2318–2335.
[https://doi.org/10.18653/v1/2024.findings-acl.137](https://doi.org/10.18653/v1/2024.findings-acl.137).

HEVNER, A. R.; MARCH, S. T.; PARK, J.; RAM, S. Design science in information
systems research. *MIS Quarterly*, v. 28, n. 1, p. 75–105, 2004.
[https://doi.org/10.2307/25148625](https://doi.org/10.2307/25148625).

HUBERT, L.; ARABIE, P. Comparing partitions. *Journal of Classification*, v. 2,
n. 1, p. 193–218, 1985.
[https://doi.org/10.1007/BF01908075](https://doi.org/10.1007/BF01908075).

ISO; IEC. *ISO/IEC 20000-1:2018: Information technology — Service management —
Part 1: Service management system requirements*. 3. ed. Geneva: ISO, 2018.
[https://www.iso.org/standard/70636.html](https://www.iso.org/standard/70636.html).

LANGE, T.; ROTH, V.; BRAUN, M. L.; BUHMANN, J. M. Stability-based validation of
clustering solutions. *Neural Computation*, v. 16, n. 6, p. 1299–1323, 2004.
[https://doi.org/10.1162/089976604773717621](https://doi.org/10.1162/089976604773717621).

MACQUEEN, J. B. Some methods for classification and analysis of multivariate
observations. In: *Proceedings of the Fifth Berkeley Symposium on Mathematical
Statistics and Probability*. Berkeley: University of California Press, 1967.
v. 1, p. 281–297.

REIMERS, N.; GUREVYCH, I. Sentence-BERT: sentence embeddings using Siamese
BERT-networks. In: *Proceedings of EMNLP-IJCNLP 2019*. Hong Kong: Association
for Computational Linguistics, 2019. p. 3982–3992.
[https://doi.org/10.18653/v1/D19-1410](https://doi.org/10.18653/v1/D19-1410).

ROUSSEEUW, P. J. Silhouettes: a graphical aid to the interpretation and
validation of cluster analysis. *Journal of Computational and Applied
Mathematics*, v. 20, p. 53–65, 1987.
[https://doi.org/10.1016/0377-0427(87)90125-7](https://doi.org/10.1016/0377-0427(87)90125-7).

SHI, L. et al. Judging the judges: a systematic study of position bias in
LLM-as-a-Judge. In: *Proceedings of IJCNLP-AACL 2025*. Mumbai: AFNLP; ACL,
2025. p. 292–314.
[https://doi.org/10.18653/v1/2025.ijcnlp-long.18](https://doi.org/10.18653/v1/2025.ijcnlp-long.18).

VINH, N. X.; EPPS, J.; BAILEY, J. Information theoretic measures for
clusterings comparison: variants, properties, normalization and correction for
chance. *Journal of Machine Learning Research*, v. 11, p. 2837–2854, 2010.
[https://www.jmlr.org/papers/v11/vinh10a.html](https://www.jmlr.org/papers/v11/vinh10a.html).

---

Pontifícia Universidade Católica do Rio de Janeiro

Curso de Pós Graduação *Business Intelligence Master*
