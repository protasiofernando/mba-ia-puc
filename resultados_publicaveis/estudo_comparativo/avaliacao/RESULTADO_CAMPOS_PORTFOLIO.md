# Informações que o usuário deve fornecer

Os campos abaixo são a decisão operacional curada. As taxas mostram, como apoio, quantas demandas históricas continham evidência de que o campo já havia sido fornecido ou estava faltando. O alinhamento foi automático com `bge-m3` (limiar principal 0.55).

A coluna principal usa somente o acordo inicial limpo entre Llama e Qwen. A faixa repete o cálculo nas quatro visões da referência. Uma contradição significa que o Stage 2 associou ao mesmo campo evidências de informação fornecida e faltante no mesmo chamado; isso é ruído potencial da extração, não um julgamento do usuário.

## Servidores Acadêmicos Compartilhados

Base histórica estrita no serviço: 419 chamados.

| Informação obrigatória | Fornecida (estrita) | Faixa 4 visões | Faltante (estrita) | Faixa 4 visões | Contradição |
|---|---:|---:|---:|---:|---:|
| Lista de usuários que precisam de acesso | 25.1% | 25.1%–27.5% | 6.4% | 6.3%–7.8% | 2.1% |
| Título da pesquisa ou identificação do projeto | 8.6% | 8.2%–9.8% | 4.1% | 3.9%–4.1% | 0.7% |
| Classificação dos dados: públicos, restritos ou confidenciais | 0.7% | 0.7%–1.0% | 0.2% | 0.2%–0.6% | 0.0% |
| Identificação do servidor, quando já existir | 62.8% | 56.8%–62.8% | 7.2% | 6.8%–7.8% | 3.6% |
| Descrição da necessidade ou do problema | 2.9% | 2.7%–3.2% | 23.2% | 19.9%–23.2% | 0.0% |

## Softwares e Licenças Acadêmicas

Base histórica estrita no serviço: 205 chamados.

| Informação obrigatória | Fornecida (estrita) | Faixa 4 visões | Faltante (estrita) | Faixa 4 visões | Contradição |
|---|---:|---:|---:|---:|---:|
| Nome e versão do software, ferramenta, pacote ou biblioteca | 40.0% | 40.0%–42.2% | 6.8% | 6.8%–7.6% | 3.4% |
| Tipo de demanda: instalação, ativação, renovação, acesso, aquisição, dúvida ou problema | 2.0% | 1.7%–2.0% | 1.5% | 1.3%–2.3% | 0.0% |
| Ambiente, servidor ou equipamento de uso | 19.5% | 19.5%–22.3% | 4.9% | 4.9%–7.0% | 1.0% |
| Usuários que precisam de acesso | 36.6% | 34.8%–36.6% | 6.8% | 6.2%–7.7% | 3.9% |
| Finalidade acadêmica ou de pesquisa | 2.9% | 2.6%–2.9% | 3.4% | 3.0%–3.4% | 0.5% |

## Nuvem Pública (AWS, Azure, GCP)

Base histórica estrita no serviço: 383 chamados.

| Informação obrigatória | Fornecida (estrita) | Faixa 4 visões | Faltante (estrita) | Faixa 4 visões | Contradição |
|---|---:|---:|---:|---:|---:|
| Provedor: AWS, Azure ou GCP | 0.5% | 0.5%–0.5% | 0.0% | 0.0%–0.0% | 0.0% |
| SI aprovada, orçamento ou centro de custo | 2.9% | 2.8%–3.0% | 7.3% | 7.3%–7.7% | 0.5% |
| Serviços e recursos desejados | 12.5% | 12.4%–12.9% | 3.7% | 3.5%–3.7% | 0.5% |
| Usuários que precisam de acesso | 55.1% | 55.1%–55.6% | 12.8% | 12.2%–13.2% | 7.0% |
| Prazo ou período de uso | 1.0% | 1.0%–1.0% | 1.3% | 1.2%–1.3% | 0.0% |

## HPC e Processamento de Alto Desempenho (GPU)

Base histórica estrita no serviço: 97 chamados.

| Informação obrigatória | Fornecida (estrita) | Faixa 4 visões | Faltante (estrita) | Faixa 4 visões | Contradição |
|---|---:|---:|---:|---:|---:|
| Finalidade do uso | 7.2% | 7.0%–7.2% | 7.2% | 7.0%–8.0% | 0.0% |
| Tipo de recurso necessário: GPU, CUDA, PBS, número de nós ou paralelização | 3.1% | 3.0%–3.1% | 10.3% | 10.0%–11.2% | 1.0% |
| Usuários que precisam de acesso | 47.4% | 46.0%–47.4% | 11.3% | 11.0%–12.0% | 7.2% |
| Necessidade de acesso externo ou VPN | 6.2% | 6.0%–6.2% | 10.3% | 10.0%–10.3% | 1.0% |
| Descrição e dimensão estimada da carga computacional | 4.1% | 4.0%–4.1% | 3.1% | 3.0%–4.1% | 0.0% |

## Máquinas Virtuais Individuais (Portal do Pesquisador)

Base histórica estrita no serviço: 98 chamados.

| Informação obrigatória | Fornecida (estrita) | Faixa 4 visões | Faltante (estrita) | Faixa 4 visões | Contradição |
|---|---:|---:|---:|---:|---:|
| Sistema operacional desejado | 12.2% | 12.1%–12.3% | 8.2% | 7.8%–8.2% | 2.0% |
| Perfil da máquina: vCPU, RAM e disco | 15.3% | 15.2%–18.1% | 22.4% | 21.6%–22.4% | 4.1% |
| Finalidade do teste ou experimento | 9.2% | 8.6%–9.2% | 8.2% | 7.8%–8.2% | 0.0% |
| Usuário responsável | 18.4% | 18.4%–21.1% | 0.0% | 0.0%–0.0% | 0.0% |
| Prazo previsto de uso | 3.1% | 2.6%–3.1% | 4.1% | 4.0%–5.3% | 1.0% |

## Submissão do Plano de Gestão de Dados (PGD) de Pesquisa

Base histórica estrita no serviço: 43 chamados.

| Informação obrigatória | Fornecida (estrita) | Faixa 4 visões | Faltante (estrita) | Faixa 4 visões | Contradição |
|---|---:|---:|---:|---:|---:|
| Título ou código do projeto de pesquisa | 34.9% | 28.1%–34.9% | 0.0% | 0.0%–0.0% | 0.0% |
| Pesquisador responsável | 27.9% | 22.8%–27.9% | 2.3% | 1.8%–2.3% | 2.3% |
| Agência de fomento, quando houver | 0.0% | 0.0%–0.0% | 0.0% | 0.0%–0.0% | 0.0% |
| Prazo para submissão ou revisão | 0.0% | 0.0%–0.0% | 11.6% | 11.6%–13.5% | 0.0% |
| Classificação conhecida ou prevista dos dados | 16.3% | 15.4%–16.3% | 7.0% | 5.3%–7.0% | 2.3% |

## Solicitação de Acesso a Bases de Dados

Base histórica estrita no serviço: 43 chamados.

| Informação obrigatória | Fornecida (estrita) | Faixa 4 visões | Faltante (estrita) | Faixa 4 visões | Contradição |
|---|---:|---:|---:|---:|---:|
| Nome da base, pasta, sistema ou repositório | 39.5% | 24.3%–53.3% | 4.7% | 4.7%–8.0% | 0.0% |
| Tipo de demanda: incluir, alterar ou excluir acesso, ingestão ou pré-processamento | 0.0% | 0.0%–1.1% | 2.3% | 1.1%–2.3% | 0.0% |
| Usuários e identificadores que precisam de acesso | 41.9% | 41.9%–44.6% | 18.6% | 9.8%–18.6% | 4.7% |
| Projeto de pesquisa, finalidade e responsável | 2.3% | 2.3%–5.4% | 0.0% | 0.0%–2.7% | 0.0% |
| Nível de permissão necessário e prazo de acesso | 11.6% | 8.7%–16.2% | 30.2% | 20.7%–30.2% | 4.7% |

## Não encontrou o que procurava?

Base histórica estrita no serviço: 13 chamados.

| Informação obrigatória | Fornecida (estrita) | Faixa 4 visões | Faltante (estrita) | Faixa 4 visões | Contradição |
|---|---:|---:|---:|---:|---:|
| Descrição detalhada da necessidade | 0.0% | 0.0%–6.7% | 53.8% | 26.7%–53.8% | 0.0% |
| Sistema, serviço ou recurso envolvido | 0.0% | 0.0%–3.3% | 0.0% | 0.0%–0.0% | 0.0% |
| Impacto e urgência | 0.0% | 0.0%–0.0% | 0.0% | 0.0%–0.0% | 0.0% |
| Unidade ou área relacionada, se conhecida | 0.0% | 0.0%–0.0% | 0.0% | 0.0%–5.0% | 0.0% |
