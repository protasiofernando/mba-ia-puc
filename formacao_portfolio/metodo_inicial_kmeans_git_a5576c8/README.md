# Triagem Inteligente de Chamados de TI com LLM Local

#### Aluno: [Fernando Nóbrega Mendes Protasio](https://github.com/protasiofernando)
#### Orientadora: [Manoela Rabello Kohler](https://github.com/manoelakohler)

---

Trabalho apresentado ao curso [BI MASTER](https://ica.puc-rio.ai/bi-master) como pré-requisito para conclusão de curso e obtenção de crédito na disciplina "Projetos de Sistemas Inteligentes de Apoio à Decisão".

- [Link para o código](https://github.com/protasiofernando/mba-ia-masterbi-puc) — o código completo do projeto está neste repositório.

- [Documentação técnica e instruções de execução](docs/README_TECNICO.md).

- Link para a monografia: em elaboração.

---

### Resumo

As áreas de suporte de TI organizam seus atendimentos em catálogos de serviços definidos, na maioria das vezes, pela intuição dos gestores — e não pela análise sistemática do que os usuários realmente solicitam. Este trabalho apresenta um sistema de apoio à decisão que reavalia o portfólio de serviços de tecnologia para pesquisa da Diretoria de Tecnologia da Informação (DTI) da Fundação Getulio Vargas (FGV) a partir do histórico real de chamados. Um pipeline de sete estágios, executado integralmente na infraestrutura de HPC da instituição, usa um modelo de linguagem local (`gemma4:26b-q8`, via Ollama, em GPU Tesla V100) para destilar a intenção de cada um dos cerca de 1,6 mil chamados históricos; agrupa os pedidos por similaridade semântica com embeddings `bge-m3` e K-means (K ótimo por coeficiente de silhueta); rotula, diagnostica e compara os grupos naturais de demanda com o catálogo vigente; e reclassifica os históricos no portfólio final definido pela curadoria humana da área. A análise revelou que o catálogo de 18 categorias não refletia a demanda real — o item genérico "Não encontrou o que procurava?" era a terceira categoria mais acionada — e que chamados abertos sem as informações necessárias, exigindo múltiplas interações de esclarecimento, levavam em média cerca de 5,5 vezes mais tempo para serem resolvidos do que os de resolução direta. O resultado é um portfólio enxuto de 7 categorias com escopo, campos obrigatórios e SLA definidos, um dashboard analítico em Flask e um assistente de triagem que classifica novos chamados em tempo real. Por rodar todo o processamento pesado localmente, nenhum dado sensível deixa a infraestrutura institucional.

### Abstract

IT support areas usually organize their services into catalogs defined by managerial intuition rather than by systematic analysis of what users actually request. This work presents a decision-support system that redesigns the research-technology service portfolio of the IT Department (DTI) at Fundação Getulio Vargas (FGV) based on the real history of support tickets. A seven-stage pipeline, executed entirely on the institution's HPC infrastructure, uses a locally hosted large language model (`gemma4:26b-q8`, served by Ollama on a Tesla V100 GPU) to distill the intent of each of roughly 1.6 thousand historical tickets; clusters requests by semantic similarity using `bge-m3` embeddings and K-means (optimal K by silhouette score); labels, diagnoses, and compares the natural demand groups against the current catalog; and reclassifies the historical tickets into the final portfolio curated by the business area. The analysis showed that the 18-category catalog did not reflect actual demand — the generic "Didn't find what you were looking for?" option was the third most used category — and that tickets opened without the required information, demanding multiple clarification exchanges, took on average about 5.5 times longer to resolve than tickets solved directly. The outcome is a lean 7-category portfolio with well-defined scope, required fields, and SLAs, an analytical Flask dashboard, and a triage assistant that classifies new tickets in real time. Because all heavy processing runs locally, no sensitive data ever leaves the institutional infrastructure.

### 1. Introdução

A DTI da FGV atende, pelo seu portal de serviços, as demandas de tecnologia dos professores e pesquisadores da instituição: acesso a servidores acadêmicos, computação em nuvem, HPC, máquinas virtuais, softwares científicos e armazenamento de dados de pesquisa. Esses atendimentos são registrados como chamados no Jira e classificados em um catálogo de 18 categorias que foi construído incrementalmente, com base na percepção dos gestores sobre a demanda.

Três evidências indicavam que esse catálogo não refletia mais a realidade. Primeiro, a opção genérica "Não encontrou o que procurava?" era a terceira categoria mais acionada (cerca de 13% dos chamados), sinal de que os usuários não localizavam onde abrir seus pedidos. Segundo, havia categorias sobrepostas disputando o mesmo tipo de solicitação. Terceiro — e mais custoso — chamados abertos sem as informações necessárias geravam idas e vindas de esclarecimento: a análise do histórico mostrou que chamados que exigiram múltiplas interações levaram, em média, cerca de 5,5 vezes mais tempo para serem resolvidos do que os atendidos de forma direta (seção 3.3).

A dificuldade clássica desse tipo de reavaliação é que o insumo relevante — o texto livre de milhares de chamados, com títulos vagos, descrições incompletas e comentários de acompanhamento — resiste às técnicas tradicionais de mineração de texto. Abordagens por frequência de termos (TF-IDF e afins) capturam vocabulário, não intenção: "não consigo usar o Stata de casa" e "solicito VPN acadêmica" são o mesmo pedido escrito de formas disjuntas. Os modelos de linguagem de grande porte (LLMs) resolvem exatamente essa lacuna, mas o uso de APIs externas esbarra em uma restrição institucional: os chamados contêm dados pessoais e não podem deixar a infraestrutura da FGV.

Este trabalho explora a viabilidade de um caminho intermediário: executar um LLM aberto de porte médio (26B de parâmetros, quantizado) na infraestrutura de HPC já existente na instituição, combinando três famílias de técnicas — sumarização estruturada por LLM, clusterização semântica por embeddings e classificação assistida por LLM — em um pipeline offline cujo resultado alimenta um sistema interativo de apoio à decisão.

O objetivo geral é redesenhar o portfólio de serviços com base em evidências, e os objetivos específicos são: (i) extrair a intenção real de cada chamado histórico, independentemente da categoria em que foi aberto; (ii) descobrir os grupos naturais de demanda sem partir das categorias existentes; (iii) diagnosticar sobreposições, lacunas e fragmentações do catálogo vigente; (iv) propor e consolidar, com curadoria humana, um portfólio otimizado com escopo, campos obrigatórios e SLA por categoria; e (v) disponibilizar um assistente de triagem que classifique novos chamados nesse portfólio em tempo real, antecipando as informações necessárias.

### 2. Modelagem

#### 2.1 Dados

A base de estudo reúne os chamados do portal de serviços de pesquisa registrados entre 2024 e 2026 — cerca de 1,6 mil chamados após deduplicação (1.575 na execução do diagnóstico; 1.583 na reclassificação final, feita sobre uma extração atualizada). Cada chamado traz título, descrição, categoria atribuída, situação, datas de criação e resolução, responsável, solicitante e o histórico de comentários. Os dados brutos contêm dados pessoais e **não são versionados** neste repositório; a pasta `data_exemplo/` traz uma base sintética de 15 chamados fictícios com o mesmo schema, que permite executar as análises em qualquer clone (ver seção 3.3).

#### 2.2 Arquitetura em três camadas

O sistema separa o processamento pesado, executado uma única vez, do uso interativo:

1. **Pipeline offline (HPC)** — sete estágios executados no nó GPU (Tesla V100 32 GB) via PBS, com o LLM `gemma4:26b-q8` e o modelo de embeddings `bge-m3` servidos localmente pelo Ollama. Consome os CSVs do Jira e persiste os resultados como JSON.
2. **Simulação de triagem** — classificação de novos chamados em tempo real, via LLM local (túnel SSH até o nó GPU) ou Azure OpenAI (opcional; recebe apenas o texto digitado na simulação, nunca dados históricos).
3. **Dashboard web (Flask + SQLite + Chart.js)** — seis abas: KPIs operacionais, categorias atuais com mapeamento, simulação de triagem, diagnóstico completo da IA, histórico reclassificado e grupos naturais de demanda.

#### 2.3 Pipeline de sete estágios

| Stage | Técnica | O que faz |
|-------|---------|-----------|
| 1 — Extração | regras | Lê os CSVs do Jira, limpa HTML/URLs/e-mails e estrutura os campos relevantes |
| 2 — Sumarização | LLM | Para cada chamado, destila um resumo estruturado: `intencao`, `tema`, `tipo_pedido`, `contexto`, campos fornecidos/faltantes e a tag `descricao_insuficiente` (se o atendente precisou pedir informações) |
| 3 — Clustering | embeddings + K-means | Gera o embedding `bge-m3` do resumo de cada chamado e agrupa por similaridade semântica; K testado de 5 a 25, escolhido por coeficiente de silhueta (K ótimo = 23) |
| 4 — Rotulação | LLM | Nomeia cada grupo e define descrição, critério de uso, campos obrigatórios e SLA |
| 5 — Comparação | LLM | Compara o catálogo vigente (com volumes reais) com os grupos naturais e gera o diagnóstico e o portfólio otimizado recomendado |
| 6 — Classificação | LLM | Reclassifica cada chamado histórico no portfólio recomendado, com justificativa e confiança |
| 7 — Finalização curada | LLM + curadoria humana | Aplica o portfólio final definido pela área (`feedback_portfolio.json`) e reclassifica os históricos nele |

O princípio central da modelagem: **o LLM entende e destila cada chamado (Stage 2) → o embedding agrupa por similaridade semântica real (Stage 3) → o LLM rotula, compara e reclassifica com contexto rico (Stages 4–6) → a curadoria humana consolida o portfólio final (Stage 7)**. Nenhum estágio usa TF-IDF ou contagem de termos: as keywords dos grupos são os campos `tema` gerados pelo LLM.

Duas decisões de projeto merecem destaque. A primeira é a separação entre o pipeline genérico e a curadoria: os Stages 1–6 não têm nenhuma regra específica da área embutida — o contexto institucional entra por configuração (`config_portfolio.json`) e as decisões de negócio (categorias finais, diretrizes, encaminhamentos) vivem em um artefato próprio (`feedback_portfolio.json`), aplicado pelo Stage 7. Isso torna o pipeline reaproveitável para qualquer área de atendimento. A segunda é a resiliência operacional: a sumarização usa checkpoint incremental (retoma do ponto exato em caso de interrupção) e todas as chamadas ao LLM passam por um cliente com retry e validação de JSON.

#### 2.4 Infraestrutura e privacidade

Todo o processamento dos dados históricos ocorre dentro da infraestrutura da FGV: o LLM roda no nó GPU do HPC institucional, servido pelo Ollama, e ocupa ~26 GB de VRAM. A escolha de um modelo aberto quantizado de 26B de parâmetros equilibra qualidade de instrução em português e viabilidade de execução em uma única V100 de 32 GB. Os arquivos com texto ou classificação por chamado são mantidos fora do versionamento; apenas agregados (grupos rotulados, diagnóstico, portfólio) são versionados. Detalhes operacionais — submissão PBS, configuração CUDA/Ollama e parâmetros de chamada do modelo — estão em [docs/MANUAL_HPC.md](docs/MANUAL_HPC.md) e [docs/NOTAS_TECNICAS.md](docs/NOTAS_TECNICAS.md).

### 3. Resultados

#### 3.1 Diagnóstico do portfólio vigente

O pipeline identificou **23 grupos naturais de demanda** — frente às 18 categorias do catálogo vigente — e evidenciou três padrões de desalinhamento: categorias amplas demais concentrando pedidos heterogêneos, demandas recorrentes sem categoria própria (que escoavam para o item genérico) e fragmentação de um mesmo tipo de pedido em categorias distintas. O item "Não encontrou o que procurava?", com 12,8% dos chamados, era a terceira categoria mais usada do catálogo.

#### 3.2 Portfólio final

Após a revisão da recomendação automática pela área (curadoria aplicada no Stage 7), o portfólio foi consolidado em **7 categorias**, nas quais os 1.583 chamados históricos foram reclassificados:

| Categoria final | Chamados |
|-----------------|---------:|
| Servidores Acadêmicos Compartilhados | 446 |
| Nuvem Pública (AWS, Azure, GCP) | 431 |
| Não encontrou o que procurava? | 247 |
| Softwares e Licenças Acadêmicas | 208 |
| Máquinas Virtuais Individuais | 123 |
| HPC e Processamento de Alto Desempenho (GPU) | 79 |
| Submissão do Plano de Gestão de Dados (PGD) de Pesquisa | 49 |

Cada categoria carrega um critério de uso (`quando_usar`), a lista de informações obrigatórias a coletar na abertura e o SLA sugerido — insumos diretos para o novo formulário do portal e para o assistente de triagem.

#### 3.3 O custo das idas e vindas — cálculo do ganho de tempo

A evidência que motiva a triagem assistida é o custo, em tempo de resolução, de um chamado aberto sem as informações necessárias. O cálculo, implementado em [`analise_tempo_interacoes.py`](analise_tempo_interacoes.py), é definido assim:

- **Interação humana**: comentário do chamado cujo autor não é o robô de automação do Jira (autor ≠ `automato`);
- **Resolução direta**: chamado resolvido com **até 1** interação humana (o pedido chegou completo);
- **Múltiplas interações**: chamado que exigiu **2 ou mais** trocas com o solicitante;
- **Tempo de resolução**: diferença entre as datas de resolução e criação, em dias; consideram-se apenas chamados com tempo válido (resolução posterior à criação);
- **Razão** = tempo(múltiplas) / tempo(direta); **ganho da resolução direta** = 1 − tempo(direta)/tempo(múltiplas).

Na base real (1.561 chamados com tempo de resolução válido):

| Grupo | n | Média | Mediana |
|-------|--:|------:|--------:|
| Resolução direta (≤1 interação humana) | 333 | 2,5 dias | 0,4 dia |
| Múltiplas interações (≥2) | 1.228 | 13,9 dias | 5,7 dias |

A razão das médias é **5,5x** (chamados com idas e vindas levam, em média, +451% de tempo); a razão das medianas é ainda maior (14,7x), porque metade dos chamados completos se resolve em menos de meio dia. Em termos de ganho: a resolução direta é **~82% mais rápida na média** e **~93% na mediana**.

Como os dados reais do Jira não são publicados, o repositório inclui a base sintética `data_exemplo/` (15 chamados fictícios, mesmo schema), que reproduz o fenômeno e permite executar o cálculo em qualquer clone:

```bash
python analise_tempo_interacoes.py --dados data_exemplo
# Razão das médias: 3,5x | ganho da resolução direta: ~72% (média)
```

**Ressalva metodológica**: trata-se de uma associação, não de uma relação causal isolada — chamados intrinsecamente mais complexos tendem tanto a exigir mais interações quanto a demorar mais. Uma análise complementar com a tag `descricao_insuficiente` (atribuída pelo LLM no Stage 2, identificando quando o atendente precisou pedir informações que o usuário poderia ter fornecido na abertura) confirma a mesma direção do efeito, com magnitude menor: chamados marcados como de descrição insuficiente levaram, em média, 1,9x mais tempo (+88%; medianas 9,0 vs 3,0 dias). O intervalo entre essas duas estimativas delimita o ganho potencial endereçável pela triagem assistida.

#### 3.4 Assistente de triagem

Com o portfólio final como contexto, o assistente classifica um chamado novo em tempo real: recebe título e descrição, devolve a categoria sugerida, a justificativa e as informações que faltam para o atendimento direto. No dashboard, a simulação funciona com o LLM local (mesmo modelo do pipeline) ou, opcionalmente, com Azure OpenAI — caso em que apenas o texto digitado é enviado, nunca dados históricos.

### 4. Conclusões

O trabalho demonstrou que é viável — técnica e institucionalmente — usar LLMs para redesenhar um portfólio de serviços a partir da demanda real, sem que nenhum dado sensível deixe a infraestrutura da organização. Três conclusões se destacam:

1. **Dados vencem intuição no desenho de catálogos.** O portfólio vigente, construído incrementalmente pela percepção dos gestores, divergia de forma mensurável da demanda real: 23 grupos naturais contra 18 categorias, com o item genérico entre os mais acionados. O portfólio final de 7 categorias cobre a mesma demanda com escopos mais claros.
2. **LLM local de porte médio é suficiente para a tarefa.** O modelo aberto quantizado de 26B, rodando em uma única V100, sustentou todas as etapas semânticas do pipeline (sumarização, rotulação, diagnóstico e classificação) com saída estruturada confiável — ao custo de um processamento offline de poucas horas, adequado para uma análise que se repete apenas periodicamente.
3. **A curadoria humana é parte do método, não um ajuste posterior.** A separação explícita entre a recomendação automática (Stages 1–6, genéricos) e a decisão de negócio (`feedback_portfolio.json`, Stage 7) foi o que tornou o resultado adotável pela área — o dashboard e o assistente sempre refletem o portfólio que a área escolheu, não o que a máquina sugeriu.

As principais limitações apontam os trabalhos futuros: o K-means impõe grupos disjuntos e o K ótimo por silhueta é sensível à composição da base; a análise de ganho de tempo mede associação, não causalidade — o desenho ideal seria comparar coortes antes/depois da adoção do novo portal; e a validação cobre um único domínio (serviços de tecnologia para pesquisa). Os próximos passos naturais são medir a adoção em produção (evolução do uso do item genérico e da taxa de resolução direta), reexecutar o pipeline periodicamente para detectar deriva da demanda e replicar o método em outras áreas de atendimento da instituição — o que o desenho genérico do pipeline já permite sem alteração de código.

---

Matrícula: pendente

Pontifícia Universidade Católica do Rio de Janeiro

Curso de Pós Graduação *Business Intelligence Master*
