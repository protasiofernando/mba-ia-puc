# Triagem Inteligente de Chamados de TI com LLM Local

#### Aluno: [Fernando Nóbrega Mendes Protasio](https://github.com/protasiofernando)
#### Matrícula: 241100336
#### Orientadora: [Manoela Rabello Kohler](https://github.com/manoelakohler)

---

Trabalho apresentado ao curso [BI MASTER](https://ica.puc-rio.ai/bi-master) como pré-requisito para conclusão de curso e obtenção de crédito na disciplina "Projetos de Sistemas Inteligentes de Apoio à Decisão".

- **Mapa da documentação:** [`docs/README.md`](docs/README.md) é o índice único
  da pasta `docs/`, com a ordem de leitura e o papel de cada arquivo.

- Primeiros destinos: [resultados do estudo](docs/RESULTADOS_COMPARACAO.md),
  [dashboard estático](resultados_publicaveis/RESULTADO_DASHBOARD.html),
  [instruções de execução](docs/README_TECNICO.md) e
  [fluxo completo do MBA](docs/FLUXO_COMPLETO_MBA.md).

- Este `README.md` funciona como síntese acadêmica do trabalho; os documentos
  vinculados preservam o detalhamento metodológico, os resultados e a auditoria.

---

> **Estado final, revisado em 10/08/2026.** Estudo concluído em HPC com GPU A100 sobre 1.456
> chamados; Job 90 com `Exit_status=0` e validação em 302 verificações, sem falhas.
> O resultado da comparação e o portfólio curado estão nas seções 4.2 e 4.6; o
> agregado do Estágio 7 está em `pipeline_data/07_portfolio_final.json`. Detalhes em
> [`docs/RESULTADOS_COMPARACAO.md`](docs/RESULTADOS_COMPARACAO.md).

> Este repositório reúne duas contribuições: a **aplicada**, o redesenho do
> portfólio da DTI Pesquisa com dashboard e curadoria estratégica, e a
> **metodológica**, a comparação entre descoberta estatística (`bge-m3` + K-means)
> e descoberta hierárquica por LLM, detalhada na seção 4.6. O
> **[dossiê de auditoria](estudo_comparativo/DOSSIE_AUDITORIA.md)** consolida os
> controles metodológicos.

### Arquitetura vigente

O repositório está organizado em três fases, que não devem ser misturadas:

1. **Formação:** o Método Estatístico produz um candidato automático nos
   Estágios 3 a 6, com implementação e linhagem em `formacao_portfolio/`.
2. **Curadoria:** a área revisa o catálogo, sem rotular chamados, e congela a
   decisão em `formacao_portfolio/decisao_curada/feedback_portfolio.json`. Depois
   do estudo, o Estágio 7 projetou automaticamente os 1.456 chamados nessa decisão.
3. **Comparação:** após o congelamento, os métodos Estatístico e Agêntico são
   reexecutados sobre o mesmo Estágio 2 para medir aderência, estabilidade e
   custo. O pacote executado contém somente código.

Componentes principais:

| Caminho | Papel |
|---|---|
| `scripts/` | Estágios, validadores, avaliador e geradores de pacote |
| `dashboard/` | Aplicação Flask local |
| `configuracao/` | Identidade, contexto institucional e catálogo real |
| `data/` | CSVs reais sensíveis, fora do Git |
| `pipeline_data/` | Artefatos agregados versionáveis e saídas locais permitidas |
| `formacao_portfolio/` | Snapshot imutável, formação e decisão curada congelada |
| `estudo_comparativo/` | Protocolo, regras, jobs PBS e roteiro operacional do estudo |
| `resultados_publicaveis/` | Relatórios, métricas e gates agregados do Job 90 |
| `docs/` | Narrativa, resultado, estado e apêndice técnico |
| `metodo_estatistico/` | Motor estatístico mantido, usado na formação e reexecutado na comparação |

### Resumo

As áreas de suporte de TI frequentemente estruturam seus catálogos de serviços
com base na experiência acumulada dos gestores, sem análise sistemática das
demandas efetivamente registradas pelos usuários. Este trabalho apresenta um
sistema de apoio à decisão para reavaliar o portfólio de serviços de tecnologia
para pesquisa da Diretoria de Tecnologia da Informação (DTI) da Fundação
Getulio Vargas (FGV) a partir do histórico de chamados. A reavaliação enfrenta
uma restrição institucional que condiciona todo o desenho: os chamados contêm
dados pessoais e não podem ser enviados a serviços externos de inteligência
artificial. Nenhum dado histórico sensível deixou a infraestrutura institucional.

O pipeline foi executado integralmente na infraestrutura de computação de alto
desempenho da instituição. Modelos de linguagem locais, `llama3.3:70b` para
raciocínio e `qwen3:30b-a3b-instruct-2507-q4_K_M` para geração de saídas
estruturadas, foram servidos pelo Ollama em uma GPU NVIDIA A100. Cada chamado
teve sua intenção identificada; os pedidos foram agrupados por intenção, e não pela
categoria em que haviam sido abertos; desses grupos derivou-se um catálogo
recomendado, no qual o histórico foi reclassificado. Como contribuição
metodológica, compararam-se duas abordagens de descoberta sob o mesmo insumo e a
mesma camada posterior: embeddings `bge-m3` combinados com K-means e descoberta
hierárquica por LLM, em três sementes, contra uma referência automática
produzida por consenso entre Llama e Qwen.

A evidência primária favoreceu K-means e o custo do método estatístico, mas não
sustentou a existência de um vencedor global único, pois os resultados variaram
conforme a semente, a camada de avaliação e a referência. O resultado
operacional consiste em um portfólio curado com sete serviços, uma categoria
residual e Sala de Sigilo como encaminhamento fixo, todos com escopo e campos
obrigatórios definidos. O que se transfere a outra instituição não é o catálogo,
que é local, mas o desenho metodológico e a demonstração de que, neste contexto,
a infraestrutura de HPC disponível foi suficiente para conduzir a análise sem
exportar dado sensível.

**Palavras-chave:** gestão de serviços de TI; mineração de chamados; modelos de
linguagem; agrupamento; apoio à decisão; catálogo de serviços.

### Abstract

IT support areas often organize service catalogs through managerial experience
rather than systematic analysis of recorded user demand. This study presents a
decision-support system that redesigns the research technology service portfolio
of Fundação Getulio Vargas using historical support tickets. The redesign faces
an institutional constraint that shapes the entire architecture: tickets contain
personal data and cannot be sent to external artificial intelligence services.
Historical sensitive data remained within the institutional infrastructure.

Locally hosted models on the institutional HPC infrastructure distilled the
intent of each ticket; requests were grouped by intent rather than by the
category under which they had been opened; a recommended catalog was derived
from those groups, and the historical records were reclassified into it. As a
methodological contribution, `bge-m3` embeddings combined with K-means were
compared with hierarchical LLM-based discovery under a shared downstream
pipeline, three random seeds, and an automatic reference produced by Llama and
Qwen.

Primary evidence favored K-means and the cost profile of the statistical
method, but did not support a unique global winner because results varied across
seeds, evaluation layers, and reference views. The operational outcome is a
curated portfolio with seven services, a residual category, and the secure-room
service as a fixed referral, each with a defined scope and required fields. What
transfers to another institution is not the catalog, which is local, but the
demonstration that already installed HPC infrastructure suffices to run the
analysis without exporting sensitive data.

**Keywords:** IT service management; ticket mining; large language models;
clustering; decision support; service catalog.

### 1. Introdução

#### 1.1 Contexto e problema

A DTI da FGV atende, por meio de seu portal de serviços, às demandas de
tecnologia de professores e pesquisadores da instituição. Entre os serviços
prestados estão o acesso a servidores acadêmicos, computação em nuvem, HPC,
máquinas virtuais, softwares científicos e armazenamento de dados de pesquisa.
Esses atendimentos são registrados no Jira e classificados em um catálogo de 18
categorias, construído incrementalmente com base na percepção dos gestores sobre
a demanda.

A gestão sistemática desses serviços envolve planejar, desenhar, entregar,
medir e melhorar os serviços para produzir valor, conforme o escopo da
ISO/IEC 20000-1 (ISO; IEC, 2018). Em centrais de atendimento, a classificação
correta já na abertura também é relevante para associar a solicitação ao serviço
adequado, reduzir encaminhamentos incorretos e diminuir o tempo de resolução
(AL-HAWARI; BARHAM, 2021). Nesse contexto, o catálogo não é apenas uma lista de
opções: ele funciona como interface entre a necessidade do usuário, a coleta de
informações e a operação que prestará o serviço.

Três evidências indicavam que o catálogo já não representava adequadamente a
demanda. Primeiro, a opção genérica "Não encontrou o que procurava?" era a
terceira categoria mais acionada na base completa, com 203 dos 1.584 chamados
(12,8%), o que sugeria dificuldade dos usuários para identificar o item correto.
Segundo, havia categorias sobrepostas para solicitações semelhantes. Terceiro, e
mais caro em termos operacionais, chamados abertos sem as informações
necessárias exigiam idas e vindas de esclarecimento. Os chamados resolvidos com
até uma interação humana levaram, em média, 2,6 dias. Os que exigiram duas ou
mais levaram 13,4.

A base original continha 1.584 chamados. Antes do Estágio 1 do pipeline, uma
regra de escopo removeu 128 registros cujo campo estruturado `Customer Request
Type` era “Solicitação de Acesso a Bases de Dados”. Esse rótulo aparecia no
portal de serviços de pesquisa avaliado neste trabalho, mas correspondia a um
fluxo de dados atendido por outra equipe, a de Banco de Dados. Ele figurava ali
por uma razão de uso: o pesquisador procura todos os serviços no mesmo portal,
ainda que a execução de alguns caiba a outra área. A remoção não dependeu de
texto livre nem de decisão de LLM. Foi feita pelo filtro do campo estruturado,
especificado pelo analista. Restaram 1.456 chamados no universo analítico.

Nesse universo, os chamados com duas ou mais interações humanas levaram, em
média, 5,22 vezes o tempo daqueles resolvidos com até uma interação. Na base
original, antes da exclusão dos 128 registros, essa razão era de 5,51. Os
valores foram calculados com as médias não arredondadas e representam uma
associação histórica, não um efeito causal (seção 4.3).

Os achados exigem interpretações distintas. A sobreposição de categorias e a
associação entre múltiplas interações e maior tempo de resolução são observadas
diretamente nos dados. Já o uso frequente do item “Não encontrou o que
procurava?” admite duas explicações: o catálogo pode não oferecer uma opção
adequada, ou a posição e a visibilidade do item no formulário podem incentivar
sua escolha. A primeira hipótese justificaria rever as categorias; a segunda,
reorganizar a interface. Os dados disponíveis não permitem separar
completamente esses efeitos.

A reavaliação é dificultada pela natureza do insumo. O texto livre de milhares
de chamados contém títulos vagos, descrições incompletas e comentários de
acompanhamento, e uma mesma intenção pode assumir diferentes formas lexicais.
Modelos de sentença baseados em Transformers foram propostos para produzir
representações semânticas comparáveis e úteis em tarefas de busca e agrupamento
(REIMERS; GUREVYCH, 2019). LLMs e embeddings ampliam essa capacidade, mas o uso
de APIs externas encontra uma restrição institucional: os chamados contêm dados
pessoais e não podem deixar a infraestrutura da FGV.

#### 1.2 Questão de pesquisa e objetivos

A questão central é: como um pipeline de inteligência artificial executado
localmente pode apoiar, de forma auditável, o redesenho de um catálogo de
serviços de TI a partir de chamados históricos? A contribuição metodológica
desdobra uma segunda questão: sob o mesmo insumo e a mesma camada semântica
posterior, como a descoberta por embeddings `bge-m3` + K-means e a descoberta
hierárquica por LLM se comparam em aderência, robustez e custo? A investigação
não pressupõe superioridade de um método e admite como resultado válido um
compromisso entre critérios ou uma conclusão dependente da camada de avaliação.

Este trabalho examina a viabilidade de executar modelos de linguagem abertos na
infraestrutura de HPC já disponível na instituição. A solução combina
sumarização estruturada por LLM, descoberta de grupos naturais (clusters) de demanda por
embeddings ou por LLM e classificação assistida por LLM. Essas técnicas integram
um pipeline offline cujos resultados alimentam um sistema interativo de apoio à
decisão.

O objetivo geral é redesenhar o portfólio de serviços com base em evidências. Os
objetivos específicos são: (i) extrair a intenção de cada chamado histórico,
independentemente da categoria de abertura; (ii) identificar grupos naturais de
demanda sem utilizar as categorias existentes como ponto de partida; (iii)
diagnosticar sobreposições, lacunas e fragmentações do catálogo vigente; (iv)
propor e consolidar, mediante curadoria humana, um portfólio com escopo, campos
obrigatórios e SLA por categoria; (v) disponibilizar um assistente de triagem
capaz de classificar novos chamados nesse portfólio em tempo real e indicar as
informações necessárias para o atendimento; e (vi) comparar a descoberta por
embeddings + K-means e a descoberta hierárquica por LLM, sob insumo e camada
posterior comuns, quanto a aderência, robustez e custo.

### 2. Fundamentação teórica

#### 2.1 Gestão de serviços e classificação de chamados

A ISO/IEC 20000-1 situa planejamento, desenho, transição, entrega e melhoria
contínua dentro de um sistema de gestão de serviços e também exige seu
monitoramento, medição e revisão (ISO; IEC, 2018). Em complemento, a ITIL 4
trata a gestão do catálogo como prática destinada a manter informações
consistentes sobre serviços e ofertas disponíveis ao público pertinente
(AXELOS, 2019). A partir dessas referências, o projeto trata o catálogo como
artefato de gestão, e não apenas como taxonomia textual, e preserva na decisão
final critérios de responsabilidade, governança e valor operacional. Essa é
uma aplicação das referências ao contexto estudado, não uma prescrição literal
da norma.

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
suporte a diferentes granularidades textuais (CHEN et al., 2024). O artigo do
modelo avalia recuperação de informação, não agrupamento; seu uso para
representar as intenções destiladas no Estágio 2 é uma adaptação metodológica
deste trabalho. Como precedente mais próximo, o IDAS produz resumos que retêm a
intenção central, codifica-os como vetores e os agrupa para descobrir intenções
latentes (DE RAEDT et al., 2023). Sobre essas representações, o K-means
particiona as observações em K grupos buscando reduzir a variabilidade interna
dos grupos (MACQUEEN, 1967).

Não existe, contudo, um número de grupos naturalmente garantido. A silhueta
avalia simultaneamente coesão interna e separação entre grupos (ROUSSEEUW,
1987), mas responde à geometria da representação e não determina, sozinha, a
utilidade de negócio do catálogo. Por isso, o projeto separa a descoberta
estatística do julgamento sobre escopo, governança e navegabilidade.

Modelos de linguagem também podem orientar o agrupamento textual por meio de
restrições semânticas e representações de grupos, em vez de atuar somente como
classificadores posteriores. O ClusterLLM demonstrou o uso de preferências
extraídas por LLM para melhorar representações e seleção de granularidade
(ZHANG; WANG; SHANG, 2023). Em centrais de contato, representações multivisão
guiadas por LLM foram aplicadas ao agrupamento hierárquico de motivos de
interação (PATTNAIK et al., 2024). Esses trabalhos documentam abordagens
relacionadas de agrupamento guiado por LLM, mas não reproduzem o segundo motor
deste estudo, que propõe grupos em lotes, atribui itens a identificadores
fechados e realiza consolidação global. Também não tornam comparáveis, por si
sós, soluções com números de grupos e processamentos posteriores distintos;
por isso, o estudo explicita separadamente o benchmark completo e a comparação
controlada.

#### 2.3 Avaliação, robustez e decisão entre humanos e sistemas de IA

Para reduzir a concordância atribuível ao acaso, o estudo utiliza o índice de
Rand ajustado (HUBERT; ARABIE, 1985) e a informação mútua ajustada (VINH; EPPS;
BAILEY, 2010). O B-cubed contabiliza precisão e revocação por elemento sem
exigir correspondência biunívoca entre os grupos das duas partições (BAGGA;
BALDWIN, 1998). Lange et al. (2004) definem estabilidade como a reprodução da
estrutura de agrupamento em outra amostra; neste trabalho, essa propriedade é
avaliada por reamostragem. A sensibilidade às sementes é tratada separadamente
como verificação complementar de robustez algorítmica, pois mede dependência da
inicialização, e não generalização para outra amostra.

O Macro-F1 com melhor correspondência por serviço, a taxa mínima de
reatribuição ao portfólio de referência e o custo computacional são medidas operacionais
definidas no protocolo deste estudo, não métricas derivadas conjuntamente das
referências anteriores. Todas são apresentadas separadamente, sem nota
composta, para que compensações arbitrárias não ocultem divergências entre
aderência, robustez e custo.

O projeto também se enquadra em *design science*: constrói e avalia artefatos
tecnológicos destinados a ampliar capacidades organizacionais (HEVNER et al.,
2004). Como escolha de governança deste projeto, a decisão final permanece sob
responsabilidade humana, enquanto a IA oferece evidências, alternativas e
projeções. No desenho da interação, essa separação é coerente com recomendações
que enfatizam explicitar capacidades, permitir correção e apoiar o usuário
quando o sistema estiver incerto (AMERSHI et al., 2019).

### 3. Modelagem

#### 3.1 Delineamento da pesquisa

Trata-se de uma pesquisa aplicada, com construção e avaliação de artefatos sob
a perspectiva de *design science*. A unidade de análise é o chamado individual;
os artefatos produzidos são o pipeline auditável, o candidato automático de
portfólio, a decisão curada, a classificação operacional e o dashboard. O
universo temporal e organizacional restringe-se aos chamados da DTI Pesquisa
da FGV entre 2024 e 2026.

A avaliação possui dois estimandos deliberadamente separados: o benchmark das
arquiteturas completas e a comparação controlada do motor de descoberta no
Estágio 3. A comparação usa o mesmo Estágio 2 congelado, a mesma interface e os
mesmos Estágios 4 a 6. Três sementes permitem observar a sensibilidade à
inicialização. A referência por chamado é automática, produzida por consenso
entre Llama e Qwen, e mede aderência ao portfólio curado, não acurácia em relação
a uma referência externa independente. Custo, aderência e estabilidade
são reportados separadamente. O protocolo e as regras de decisão foram
registrados antes da avaliação final em
[`estudo_comparativo/PROTOCOLO_METODOLOGICO.md`](estudo_comparativo/PROTOCOLO_METODOLOGICO.md).

#### 3.2 Dados

A base original reúne os chamados registrados no portal de serviços de pesquisa
entre 2024 e 2026, totalizando **1.584 registros** após a deduplicação. Para a
comparação, uma regra exata aplicada ao campo `Customer Request Type` removeu
128 registros antes do Estágio 1, o que resultou em um universo analítico de
**1.456 chamados**. Todos os registros removidos apresentavam o rótulo legado
**“Solicitação de Acesso a Bases de Dados”**, correspondente ao fluxo de dados
confidenciais da Sala de Sigilo, atendido fora da DTI Pesquisa pela equipe de
Banco de Dados. Além disso, os outros seis rótulos da lista de exclusão tiveram zero ocorrências no período.

O item legado removido não corresponde ao serviço homônimo do portfólio curado.
O serviço final contempla o acesso comum a pastas e bases de pesquisa **fora da
Sala de Sigilo** e substitui a categoria “Acessar pastas de dados de pesquisa”.
A distinção institucional e as respectivas contagens estão documentadas em
[`configuracao/contexto_catalogo.md`](configuracao/contexto_catalogo.md), e a
decisão curada está registrada em
[`feedback_portfolio.json`](formacao_portfolio/decisao_curada/feedback_portfolio.json).

Cada chamado contém título, descrição, categoria atribuída, situação, datas,
responsáveis e comentários. Como os dados brutos contêm informações pessoais,
eles não são versionados. O script `scripts/gerar_base_sintetica.py` produz, em
`data_exemplo/`, uma amostra inteiramente artificial com o mesmo esquema para
fins de demonstração. O gerador utiliza somente o catálogo agregado público e,
por política de publicação, nenhum arquivo CSV integra este repositório. Todos
os resultados quantitativos apresentados no trabalho foram calculados sobre a
base real, dentro da infraestrutura da FGV.

#### 3.3 Arquitetura em três camadas

O sistema separa o processamento pesado, executado uma única vez, do uso interativo:

1. **Pipeline offline (HPC):** os Estágios 1 a 6 processam os CSVs do Jira no nó
   com GPU e persistem os resultados em JSON.
2. **Simulação de triagem:** novos chamados são classificados em tempo real por
   um LLM local, acessado por túnel SSH até o nó com GPU, ou opcionalmente pelo
   Azure OpenAI. Neste último caso, são enviados o texto inserido, o catálogo
   agregado e o contexto institucional configurado no prompt; os chamados
   históricos não são transmitidos. O fallback em nuvem só deve ser habilitado
   quando esse envio estiver autorizado pela política institucional.
3. **Dashboard web:** a aplicação utiliza Flask, SQLite e Chart.js e apresenta
   as abas Tipos de Chamado Sugeridos, Indicadores, Prévia do Portal e Histórico.

#### 3.4 Pipeline de sete estágios

| Estágio | Técnica | O que faz |
|-------|---------|-----------|
| 1. Extração | regras | Lê os CSVs do Jira, limpa HTML, URLs e endereços de e-mail e estrutura os campos relevantes |
| 2. Sumarização | LLM | Para cada chamado, produz um resumo estruturado com intenção, tema, tipo de pedido, contexto, campos fornecidos ou faltantes e a marcação `descricao_insuficiente` |
| 3. Descoberta de grupos | `bge-m3` + K-means ou LLM hierárquica | A formação inicial usou o motor estatístico; o segundo método usa descoberta por LLM; a comparação reexecuta ambos sob uma interface comum |
| 4. Rotulação | LLM | Nomeia cada grupo e define sua descrição, seu critério de uso, seus campos obrigatórios e seu SLA |
| 5. Comparação | LLM | Compara o catálogo vigente com os grupos naturais e gera o diagnóstico e a recomendação de portfólio |
| 6. Classificação | LLM | Reclassifica cada chamado histórico no portfólio recomendado, com justificativa e confiança |
| 7. Finalização curada | curadoria humana e projeção automática | Congela a decisão em `formacao_portfolio/decisao_curada/feedback_portfolio.json`; `materializar_portfolio_curado.py` cria o agregado e `run_stage7_curadoria.py` classifica os chamados sem rótulos manuais |

Essa sequência separa interpretação, descoberta, recomendação, decisão humana e
projeção automática. O [fluxo completo](docs/FLUXO_COMPLETO_MBA.md) também
distingue estágios do pipeline de jobs de execução. Nenhum estágio usa TF-IDF ou
contagem de termos: as palavras-chave dos grupos são os campos `tema` gerados
pelo LLM.

Duas decisões completam a modelagem. O Estágio 5 recomenda; a área decide em
`formacao_portfolio/decisao_curada/`; e o materializador verifica se
`portfolio_referencia.json` espelha `feedback_portfolio.json` antes da projeção
automática. Para resiliência, sumarização e classificação usam pontos de controle
vinculados ao conteúdo, tentativas controladas e validação de JSON.

#### 3.5 Infraestrutura e privacidade

Todo o processamento dos dados históricos ocorre dentro da infraestrutura da
FGV. Os modelos são executados no nó com GPU NVIDIA A100 do HPC institucional e
servidos pelo Ollama. A escolha de `llama3.3:70b` para as tarefas de raciocínio
e de `qwen3:30b-a3b-instruct-2507-q4_K_M` para gerar a saída estruturada em JSON
busca equilibrar a qualidade das instruções em português e a viabilidade da
execução local. Arquivos com texto ou classificação por chamado permanecem fora
do versionamento; somente dados agregados são publicados. Os detalhes
operacionais estão em [docs/MANUAL_HPC.md](docs/MANUAL_HPC.md).

### 4. Resultados e discussão

#### 4.1 Diagnóstico do portfólio vigente

O catálogo vigente oferecia 18 categorias. Nas três configurações observadas, a
reconstrução da estrutura da demanda diretamente a partir dos chamados encontrou
mais grupos do que o catálogo vigente. O recorte histórico que iniciou a
formação do portfólio continha **23 grupos**; a execução comparativa final
produziu **29 grupos** no Método Estatístico e **20 tipos de requisição** no
Método Agêntico, antes da consolidação semântica. As três quantidades pertencem
a etapas distintas e não devem ser interpretadas como resultados equivalentes,
mas apontam na mesma direção: categorias excessivamente amplas, demandas
recorrentes sem categoria própria e fragmentação de pedidos semelhantes.

O sintoma mais visível desse desalinhamento estava dentro do próprio catálogo.
Na base completa de 1.584 chamados, o item “Não encontrou o que procurava?”
reunia 203 casos (12,8%) e era a terceira categoria mais utilizada. Portanto,
quase um em cada oito chamados foi aberto pelo item genérico. Esse uso pode
indicar dificuldade de localização, mas também pode refletir a posição e a
visibilidade do item na interface. O percentual descreve o diagnóstico anterior
ao filtro e não a distribuição do universo comparativo de 1.456 registros.

#### 4.2 Portfólio final

Após a revisão da recomendação automática pela área, o portfólio final curado
organiza a demanda em **7 serviços**, uma categoria residual (*catch-all*) e o
encaminhamento fixo
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
| Triagem | Não encontrou o que procurava? | categoria residual |
| Encaminhamentos | Sala de Sigilo | visível, imutável e fora da análise |

Cada categoria carrega um critério de uso (`quando_usar`), a lista de
informações obrigatórias a coletar na abertura e o SLA sugerido. Esses elementos
constituem insumos diretos para o novo formulário do portal e para o assistente
de triagem. O Estágio 7 vigente foi materializado automaticamente depois do
encerramento do estudo. A projeção operacional, que não altera as métricas
comparativas, foi:

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

- **Interação humana:** comentário do chamado cujo autor não é o robô de
  automação do Jira, identificado como `automato`.
- **Resolução direta:** chamado resolvido com até uma interação humana.
- **Múltiplas interações:** chamado com dois ou mais comentários humanos. A
  métrica não distingue, nos comentários sucessivos, mensagens internas de
  trocas efetivas com o solicitante.
- **Tempo de resolução:** diferença, em dias, entre as datas de resolução e
  criação. São considerados apenas chamados com tempo válido, cuja resolução é
  posterior à criação.
- **Razão descritiva:** tempo médio do grupo com múltiplas interações dividido
  pelo tempo médio do grupo com resolução direta.

Como o diagnóstico operacional foi calculado antes da definição do recorte
comparativo, há dois denominadores legítimos. Eles são declarados separadamente:

| Universo | Tempo válido | Direta (n; média; mediana) | Múltiplas (n; média; mediana) | Razão das médias | Razão das medianas |
|---|---:|---|---|---:|---:|
| Base completa pré-filtro | 1.561 | 333; 2,5 dias; 0,4 dia | 1.228; 13,9 dias; 5,7 dias | 5,51x | 14,75x |
| Universo analítico pós-filtro | 1.440 | 329; 2,6 dias; 0,4 dia | 1.111; 13,4 dias; 5,8 dias | 5,22x | 14,01x |

As razões foram calculadas com as médias e as medianas sem arredondamento; por
isso não reproduzem a divisão direta dos valores exibidos na tabela, que
aparecem arredondados. Por exemplo, 13,4 / 2,6 dá 5,15, enquanto a razão real
das médias é 5,22.

No ambiente interno, o comando sem argumentos lê o diretório privado `data/`,
que contém o universo analítico de 1.456 registros, e portanto reproduz
**5,22x**. O valor **5,51x** requer a cópia privada anterior ao filtro, com
1.584 registros, informada por meio do argumento `--dados`. Essa base não pode
ser publicada. Os valores descrevem os grupos históricos e
não estimam quanto tempo seria economizado ao alterar o formulário.

Como os dados reais do Jira não são publicados, `scripts/gerar_base_sintetica.py`
gera em `data_exemplo/` uma amostra inteiramente artificial para demonstrar o
cálculo, nos termos descritos na seção 3.2. O CSV gerado permanece ignorado pelo
Git.

Depois de gerar a base sintética:

```bash
python scripts/gerar_base_sintetica.py
python scripts/analise_tempo_interacoes.py --dados data_exemplo
```

Os números sintéticos servem somente para verificar a execução.

**Ressalva metodológica:** trata-se de uma associação, não de uma relação causal
isolada. Chamados intrinsecamente mais complexos tendem a exigir mais interações
e também a apresentar maior tempo de resolução. O trabalho usa essa evidência
para motivar a coleta de campos, mas não quantifica um ganho causal atribuível
ao novo formulário. Uma análise exploratória baseada na marcação
`descricao_insuficiente` não é reportada numericamente porque seu agregado e
seus denominadores não integram o conjunto publicável atual.

#### 4.4 Assistente de triagem

Com o portfólio final como contexto, o assistente classifica novos chamados em
tempo real. O sistema recebe título e descrição e retorna a categoria sugerida,
a justificativa e as informações ainda necessárias para o atendimento direto.
No dashboard, a simulação utiliza o mesmo modelo local do pipeline ou,
opcionalmente, o Azure OpenAI. Nesse segundo caso, são enviados o texto
inserido, o catálogo agregado e o contexto institucional configurado; os
chamados históricos não são transmitidos. Por isso, o modo Azure depende de
autorização institucional explícita.

O assistente é uma prova de conceito funcional. O teste automatizado verifica o
contrato de resposta e o enriquecimento pelo catálogo, mas o trabalho não mede
sua acurácia em novos chamados rotulados, sua latência em produção nem sua
usabilidade com solicitantes. Essas três medidas permanecem como critérios de
aceitação para uma implantação operacional.

#### 4.5 Reprodutibilidade e demonstração

Qualquer pessoa que clone este repositório consegue executar o painel localmente:

```bash
pip install -r requirements.txt
python dashboard/app.py   # http://localhost:5000
```

- A aba **Tipos de Chamado Sugeridos** apresenta os resultados agregados reais
  do pipeline, versionados em `pipeline_data/` sem dados pessoais. A visualização
  reúne o diagnóstico executivo, o portfólio curado, a projeção agregada do
  Estágio 7 e a consolidação do catálogo.
- As abas **Indicadores** e **Histórico** dependem de `dashboard/runtime/knowledge_base.db`. Qualquer pessoa pode gerar a base artificial com `python scripts/gerar_base_sintetica.py` e, depois, usar `$env:JIRA_DATA_DIR="data_exemplo"; python scripts/knowledge_base.py`. Esses indicadores são demonstrativos; os resultados oficiais são os agregados versionados.
- A aba **Prévia do Portal** mostra o catálogo proposto. A simulação ao vivo
  usa Ollama local quando `OLLAMA_MODEL` está definido. O Azure OpenAI funciona
  apenas como alternativa opcional quando endpoint e chave são fornecidos
  localmente e existe um deployment compatível; nenhuma credencial é
  distribuída no repositório.
  `DASHBOARD_LLM_PROVIDER` permite escolher explicitamente o motor.
- A associação entre tempo e interações (seção 4.3) pode rodar sobre a base
  sintética depois que ela for gerada.
- **Comparação dos dois métodos:** desenho, status, linhagem e execução em
  [estudo_comparativo/DOSSIE_AUDITORIA.md](estudo_comparativo/DOSSIE_AUDITORIA.md).

As instruções completas de instalação e execução estão em [docs/README_TECNICO.md](docs/README_TECNICO.md).

#### 4.6 Comparação robusta dos métodos de descoberta

O estudo preserva dois estimandos:

1. o benchmark descritivo das arquiteturas completas;
2. a comparação controlada do Estágio 3, com insumo, campos, interface e
   Estágios 4 a 6 comuns a K-means e LLM.

No benchmark, vários componentes mudam ao mesmo tempo; por isso, suas diferenças
não podem ser atribuídas isoladamente ao motor de descoberta.

Ambos os desenhos partem do mesmo Estágio 2 congelado, com 1.456 chamados,
produzido após a remoção determinística dos 128 registros descrita na seção 3.2.
Nenhuma LLM ou texto livre decide o escopo.

A comparação controlada usa três pares de sementes e uma referência automática
produzida por Llama e Qwen em quatro visões. A métrica principal dá o mesmo peso
aos serviços; ARI e outras métricas são secundárias, sem nota composta. Como o
alvo é o portfólio adotado, a análise mede aderência à decisão da área, não
acurácia ante uma referência externa independente. O custo dos Estágios 3 a 6 é
medido separadamente.

O **Macro-F1 por serviço** mede quanto os grupos produzidos recuperam os sete
serviços substantivos do portfólio. Para cada serviço, o F1 combina precisão
(quanto do grupo correspondente pertence àquele serviço) e revocação (quanto
daquele serviço foi recuperado pelo grupo). Em seguida, calcula-se a média dos
sete F1, dando o mesmo peso a serviços grandes e pequenos; a categoria residual
fica fora. O resultado varia de 0 a 1, e valores maiores indicam maior aderência.
Por ser uma média por serviço com melhor correspondência entre grupos, não deve
ser lido como percentual simples de chamados classificados corretamente.

O símbolo **Δ** representa a subtração `Macro-F1 do LLM − Macro-F1 do K-means`.
Assim, Δ negativo favorece K-means e Δ positivo favorece LLM. A margem prática
pré-registrada foi 0,03: diferenças de até 0,03 em módulo são tratadas como
materialmente equivalentes naquele recorte. As sementes são números usados para
inicializar componentes pseudoaleatórios; o mesmo valor é aplicado aos dois
métodos em cada par.

| Semente | Macro-F1 K-means | Macro-F1 LLM | Δ (LLM − K-means) | Leitura pela margem de 0,03 |
|---:|---:|---:|---:|---|
| 42 | 0,642 | 0,518 | -0,124 | K-means, por 12,4 pontos de Macro-F1 |
| 27.182 | 0,611 | 0,560 | -0,051 | K-means, por 5,1 pontos |
| 31.415 | 0,554 | 0,556 | +0,002 | equivalentes; diferença de 0,2 ponto |

Por exemplo, na semente 42, `0,518 − 0,642 = −0,124`: o sinal negativo mostra
que o K-means teve o maior Macro-F1, e o módulo indica uma distância de 0,124 na
escala de 0 a 1, ou 12,4 pontos na escala de 0 a 100.

| Métrica secundária, semente 42 | K-means | LLM | Leitura material |
|---|---:|---:|---|
| B-cubed F1 | 0,424 | 0,417 | equivalente |
| ARI | 0,282 | 0,238 | K-means |
| AMI | 0,531 | 0,403 | K-means |
| Reatribuição mínima | 18,1% | 32,4% | K-means |

Essas métricas respondem a perguntas diferentes. O **B-cubed F1** avalia, por
chamado, a pureza e a cobertura dos grupos; **ARI** mede a concordância global
entre pares de chamados, corrigida pelo acaso; **AMI** mede a informação
compartilhada entre as duas partições, também corrigida pelo acaso. Nessas três,
valores maiores são melhores. A **reatribuição mínima** estima a menor parcela
de chamados que precisaria mudar depois de cada grupo predito ser renomeado como
seu serviço de referência mais frequente; nela, valores menores são melhores.

No custo comparável dos Estágios 3 a 6, as arquiteturas completas consumiram
2,01 h no caminho estatístico e 4,60 h no agêntico, redução de 56,3%. Entre os
motores controlados, as medianas foram 1,69 h e 4,41 h, respectivamente,
redução de 61,6%. As tabelas completas, incluindo intervalos bootstrap,
energia, tokens e as quatro visões da referência, permanecem no relatório de
resultados.

**Resultado:** A evidência primária e o custo favorecem K-means, mas a
dependência da camada impede declarar um vencedor global único de aderência.
Consulte a
[linhagem das tentativas](docs/APENDICE_TECNICO.md) e as
[tabelas completas](docs/RESULTADOS_COMPARACAO.md).

#### 4.7 Discussão integrada

O pipeline transformou chamados históricos em evidência auditável sem exportar
dados sensíveis, mas não determinou sozinho o portfólio. A área converteu padrões
de demanda em serviços com responsabilidade, escopo e campos de abertura; só
então o Estágio 7 projetou o histórico na decisão congelada. Essa sequência liga
problema, construção e utilidade, como propõe a *design science* (HEVNER et al.,
2004), e mantém a decisão humana corrigível e explícita (AMERSHI et al., 2019).

Categorias sobrepostas e o uso elevado do item genérico são coerentes com o
risco de encaminhamento inadequado descrito por Al-Hawari e Barham (2021). A
projeção de 1,6% do histórico na categoria residual indica cobertura
retrospectiva mais específica, mas não prova que usuários futuros escolherão os
novos itens corretamente.

Na comparação metodológica, K-means apresentou o melhor compromisso entre a
evidência primária e o custo deste domínio, não superioridade universal. A
variação entre sementes, camadas e referências confirma que coesão, concordância
externa e estabilidade medem propriedades distintas (ROUSSEEUW, 1987; LANGE et
al., 2004; VINH; EPPS; BAILEY, 2010).

A associação entre interações e duração sustenta a coleta de campos obrigatórios,
mas não uma promessa causal de redução de tempo, pois complexidade, prioridade e
disponibilidade da equipe podem afetar ambas. Em síntese, a automação produziu
grupos, volumes, sobreposições e medidas de custo e tempo; a decisão continuou
dependente de responsabilidade, governança e visibilidade, critérios ausentes do
histórico.

#### 4.8 Ameaças à validade

- **Validade de construto:** o portfólio curado é uma decisão operacional da
  própria área, não uma referência externa independente. O consenso entre Llama
  e Qwen reduz a dependência de um único modelo, mas a referência continua
  automática e não há amostra de rótulos humanos por chamado. Além disso, as
  quatro visões derivam dos mesmos dois modelos, portanto seus erros podem ser
  correlacionados e não equivalem a quatro referências independentes. Estudos
  sobre
  avaliadores baseados em LLM demonstram a ocorrência de viés de posição nos
  julgamentos (SHI et al., 2025). Por isso, o trabalho interpreta as métricas
  como aderência ao alvo adotado, e não como acurácia absoluta.
- **Validade interna:** as três sementes e a camada comum dos Estágios 4 a 6
  controlam
  parte da variabilidade, mas não eliminam a não determinação dos modelos. A
  semente altera a inicialização do K-means, enquanto no motor agêntico altera a
  ordem dos lotes; os pares são perturbações com o mesmo identificador, não
  réplicas estocásticas perfeitamente equivalentes. O portfólio usado como alvo
  também foi informado por um candidato inicial do Método Estatístico. A
  análise de interações e tempo é observacional e não controla todos os fatores
  de complexidade; nenhuma conclusão causal é formulada.
- **Validade externa:** os dados pertencem a uma única área de serviços de TI,
  em uma instituição e janela temporal específicas. A arquitetura é
  transferível, mas os serviços descobertos, limiares e custos não devem ser
  generalizados sem nova execução e validação local.
- **Validade de conclusão:** Macro-F1, B-cubed, ARI, AMI, reatribuição e custo
  reduzem a dependência de uma única métrica; três sementes, porém, não cobrem
  toda a variabilidade possível. O pareamento de melhor correspondência usado
  no Macro-F1 é permissivo e os métodos produziram cardinalidades diferentes
  (K-means: 23, 27 e 28 grupos; LLM: 19, 19 e 20), sem uma análise de
  sensibilidade com K fixo. Os intervalos bootstrap reamostram chamados como
  observações independentes e são condicionais ao desenho executado. A
  conclusão conservadora, que reconhece a ausência
  de um vencedor global único, respeita essa limitação.
- **Reprodutibilidade e privacidade:** código, configurações, hashes, resultados
  agregados e 302 verificações são públicos. Textos e classificações por chamado não
  podem ser divulgados, o que limita a reprodução independente dos números
  exatos e a avaliação fora da amostra, mas preserva a obrigação institucional
  de proteção dos dados.
- **Auditabilidade temporal:** o repositório público foi consolidado depois da
  execução e publicou regras e resultados no mesmo commit-raiz. Assim, seu
  histórico Git não comprova de forma independente a anterioridade temporal do
  pré-registro. Manifestos, hashes, timestamps de jobs e o apêndice técnico
  preservam a proveniência interna, mas não equivalem a um carimbo de tempo de
  terceiro. Uma replicação futura deve registrar protocolo e regras em serviço
  externo imutável antes de liberar os resultados.

### 5. Conclusões

O trabalho demonstrou a viabilidade técnica e institucional de redesenhar o
portfólio com LLMs locais e dados históricos protegidos. Quatro conclusões se
destacam:

1. **Dados qualificam a decisão gerencial.** Os 18 itens vigentes não refletiam
   toda a estrutura observada nos chamados. A curadoria converteu essa evidência
   em sete serviços, uma categoria residual e Sala de Sigilo como encaminhamento
   fixo; o Estágio 7 projetou 1,6% do histórico na categoria residual, proporção
   que ainda precisa ser medida em produção.
2. **Modelos abertos e locais são viáveis neste contexto.** `llama3.3:70b` e
   `qwen3:30b-a3b-instruct-2507-q4_K_M` foram executados na A100 e sustentaram
   as etapas semânticas em duração compatível com análises periódicas.
3. **A curadoria humana é parte do método.** A separação entre recomendação e
   decisão permite considerar responsabilidade, governança e visibilidade, não
   apenas volume. Sala de Sigilo permanece fixa e fora da comparação.
4. **A comparação deve separar aderência, robustez e custo.** A evidência
   primária e o custo favorecem K-means, mas a sensibilidade à camada impede
   declarar vencedor global único.

As limitações da seção 4.8 orientam os próximos testes: comparar coortes antes e
depois da implantação, replicar o estudo em outros domínios e monitorar adoção,
uso do item genérico e resolução direta. Só a operação poderá mostrar se o
catálogo baseado na demanda histórica é mais fácil de usar e quando o pipeline
deve ser reexecutado para captar mudanças nessa demanda.

### 6. Transparência sobre uso de IA

Modelos locais integram o objeto técnico da pesquisa e executaram as etapas
semânticas descritas no método. Ferramentas de IA generativa foram utilizadas
exclusivamente como apoio à revisão de código, documentação e redação. Todas as
decisões metodológicas, interpretações, verificações e conclusões são de
responsabilidade exclusiva do autor. Nenhum texto histórico de chamado foi
enviado a esses serviços externos.

### 7. Referências

AL-HAWARI, F.; BARHAM, H. A machine learning based help desk system for IT
service management. *Journal of King Saud University – Computer and Information
Sciences*, v. 33, n. 6, p. 702–718, 2021.
[https://doi.org/10.1016/j.jksuci.2019.04.001](https://doi.org/10.1016/j.jksuci.2019.04.001).

AMERSHI, S. et al. Guidelines for human-AI interaction. In: *CHI Conference on
Human Factors in Computing Systems Proceedings*. New York: ACM, 2019. p. 1–13.
[https://doi.org/10.1145/3290605.3300233](https://doi.org/10.1145/3290605.3300233).

AXELOS. *ITIL Foundation: ITIL 4 Edition*. Norwich: The Stationery Office,
2019. ISBN 978-0-11-331607-6.

BAGGA, A.; BALDWIN, B. Entity-based cross-document coreferencing using the
vector space model. In: *Proceedings of COLING-ACL 1998*. Montreal: Association
for Computational Linguistics, 1998. p. 79–85.
[https://doi.org/10.3115/980845.980859](https://doi.org/10.3115/980845.980859).

CHEN, J. et al. M3-Embedding: multi-linguality, multi-functionality,
multi-granularity text embeddings through self-knowledge distillation. In:
*Findings of the Association for Computational Linguistics: ACL 2024*.
Bangkok: Association for Computational Linguistics, 2024. p. 2318–2335.
[https://doi.org/10.18653/v1/2024.findings-acl.137](https://doi.org/10.18653/v1/2024.findings-acl.137).

DE RAEDT, M.; GODIN, F.; DEMEESTER, T.; DEVELDER, C. IDAS: intent discovery
with abstractive summarization. In: *Proceedings of the 5th Workshop on NLP for
Conversational AI*. Toronto: Association for Computational Linguistics, 2023.
p. 71–88.
[https://doi.org/10.18653/v1/2023.nlp4convai-1.7](https://doi.org/10.18653/v1/2023.nlp4convai-1.7).

HEVNER, A. R.; MARCH, S. T.; PARK, J.; RAM, S. Design science in information
systems research. *MIS Quarterly*, v. 28, n. 1, p. 75–105, 2004.
[https://doi.org/10.2307/25148625](https://doi.org/10.2307/25148625).

HUBERT, L.; ARABIE, P. Comparing partitions. *Journal of Classification*, v. 2,
n. 1, p. 193–218, 1985.
[https://doi.org/10.1007/BF01908075](https://doi.org/10.1007/BF01908075).

ISO; IEC. *ISO/IEC 20000-1:2018: Information technology: Service management:
Part 1: Service management system requirements*. 3. ed. Geneva: ISO, 2018.
[https://www.iso.org/standard/70636.html](https://www.iso.org/standard/70636.html).

LANGE, T.; ROTH, V.; BRAUN, M. L.; BUHMANN, J. M. Stability-based validation of
clustering solutions. *Neural Computation*, v. 16, n. 6, p. 1299–1323, 2004.
[https://doi.org/10.1162/089976604773717621](https://doi.org/10.1162/089976604773717621).

MACQUEEN, J. B. Some methods for classification and analysis of multivariate
observations. In: *Proceedings of the Fifth Berkeley Symposium on Mathematical
Statistics and Probability*. Berkeley: University of California Press, 1967.
v. 1, p. 281–297.
[https://digicoll.lib.berkeley.edu/record/113015](https://digicoll.lib.berkeley.edu/record/113015).

PATTNAIK, A.; GEORGE, C.; TRIPATHI, R. K.; VUTLA, S.; VEPA, J. Improving
hierarchical text clustering with LLM-guided multi-view cluster representation.
In: *Proceedings of the 2024 Conference on Empirical Methods in Natural
Language Processing: Industry Track*. Miami: Association for Computational
Linguistics, 2024. p. 719–727.
[https://doi.org/10.18653/v1/2024.emnlp-industry.54](https://doi.org/10.18653/v1/2024.emnlp-industry.54).

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

ZHANG, Y.; WANG, Z.; SHANG, J. ClusterLLM: large language models as a guide for
text clustering. In: *Proceedings of the 2023 Conference on Empirical Methods
in Natural Language Processing*. Singapore: Association for Computational
Linguistics, 2023. p. 13903–13920.
[https://doi.org/10.18653/v1/2023.emnlp-main.858](https://doi.org/10.18653/v1/2023.emnlp-main.858).

---

Pontifícia Universidade Católica do Rio de Janeiro

Curso de Pós Graduação *Business Intelligence Master*
