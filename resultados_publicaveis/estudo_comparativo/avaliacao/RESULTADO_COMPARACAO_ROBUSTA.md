# Resultado da comparação robusta de métodos

> O alvo é o portfólio operacional curado ex post. A máscara de Sala de Sigilo é automática e conservadora: qualquer voto de Sala, ambiguidade ou baixa confiança põe o caso em quarentena antes dos métodos e métricas. Isso reduz risco de inclusão, mas não constitui prova externa de escopo.

## Conclusão integrada

**resultado_global_nao_unico** (força: `condicional_ou_provisoria`).

O benchmark operacional e a ablacao respondem perguntas diferentes. A aderencia so e sintetizada quando as direcoes sao estaveis; o benchmark operacional continua condicionado a uma unica execucao. Custo e sintetizado separadamente e nunca e ocultado por uma conclusao de aderencia. O alvo curado nao vira verdade externa.

Decisão operacional: **portfolio_curado_permanece_adotado**.

Síntese de custo: **custo_convergente_estatistico** (disponível nos dois estimandos: `True`; convergente: `True`).
Vencedores de custo — benchmark: `m1`; ablação: `kmeans`.

## Dois estimandos, duas conclusões

### 1. Benchmark das arquiteturas downstream (Stages 3–6)

**operacional_inconclusivo_dependente_da_camada** (força: `descritiva_inconclusiva`).

benchmark das arquiteturas downstream nos Stages 3-6, condicionado ao mesmo Stage 2; o M1 e a arquitetura legada reexecutada do zero com Llama; uma unica execucao nao identifica causalmente qual componente explica a diferenca nem estima variancia entre execucoes.

| Visão | Camada | Δ Macro-F1 (M2 − M1) | Direção |
|---|---|---:|---|
| consensus_strict | discovery | -0.092 | m1 |
| consensus_strict | final_request_types | +0.202 | m2 |
| consensus_strict | final_groups | +0.107 | m2 |
| consensus_full | discovery | -0.060 | m1 |
| consensus_full | final_request_types | +0.199 | m2 |
| consensus_full | final_groups | +0.090 | m2 |
| model_a | discovery | -0.068 | m1 |
| model_a | final_request_types | +0.186 | m2 |
| model_a | final_groups | +0.070 | m2 |
| model_b | discovery | -0.091 | m1 |
| model_b | final_request_types | +0.190 | m2 |
| model_b | final_groups | +0.070 | m2 |

Visão primária: `consensus_full`. Cada visão recebe bootstrap próprio:

| Visão | N | Δ médio | IC 95% | Exclui zero | IC inteiro em ±0,03 |
|---|---:|---:|---|---|---|
| consensus_strict | 1301 | +0.202 | [+0.176; +0.226] | True | False |
| consensus_full | 1456 | +0.198 | [+0.174; +0.224] | True | False |
| model_a | 1456 | +0.186 | [+0.161; +0.212] | True | False |
| model_b | 1456 | +0.189 | [+0.166; +0.211] | True | False |

Gates auditáveis do benchmark:

| Gate | Resultado |
|---|---|
| Referências completas | True |
| Sensível à referência | False |
| Sensível à camada | True |
| Conflito nas métricas secundárias | False (dominância: nenhuma) |
| Proteção estratégica (4 refs, request types) | True (4/4; não avaliáveis: 0) |
| Todos os ICs excluem zero | True |
| Todos os ICs inteiros na equivalência | False |
| Custo disponível / vencedor / gap | True / m1 / 56.3% |

| Serviço protegido | Pior margem do vencedor no benchmark | Limite |
|---|---:|---:|
| HPC e Processamento de Alto Desempenho (GPU) | +0.238 | -0.100 |
| Máquinas Virtuais Individuais (Portal do Pesquisador) | +0.151 | -0.100 |
| Submissão do Plano de Gestão de Dados (PGD) de Pesquisa | +0.634 | -0.100 |
| Solicitação de Acesso a Bases de Dados | +0.038 | -0.100 |

### 2. Ablação justa do motor de descoberta

**inconclusivo_dependente_da_camada** (força: `inconclusiva_apos_testes_de_robustez`).

Nos braços `*_common_*`, variam os motores K-means e LLM. Eles recebem os mesmos campos semânticos; a categoria histórica e o contexto legado são removidos, e a interface canônica e os Stages 4–6 são iguais. A LLM recebe somente um identificador técnico opaco para devolver cada atribuição; a chave Jira e seu possível sinal sequencial não entram no prompt.

| Visão da referência | Cobertura | Δ Macro-F1 (LLM − K-means) | Direção |
|---|---:|---:|---|
| consensus_strict | 89.4% | -0.134 | kmeans |
| consensus_full | 100.0% | -0.124 | kmeans |
| model_a | 100.0% | -0.117 | kmeans |
| model_b | 100.0% | -0.129 | kmeans |

Visão primária: `consensus_full`. Cada visão recebe bootstrap próprio:

| Visão | N | Δ médio | IC 95% | Exclui zero | IC inteiro em ±0,03 |
|---|---:|---:|---|---|---|
| consensus_strict | 1301 | -0.133 | [-0.167; -0.101] | True | False |
| consensus_full | 1456 | -0.125 | [-0.155; -0.095] | True | False |
| model_a | 1456 | -0.116 | [-0.147; -0.086] | True | False |
| model_b | 1456 | -0.130 | [-0.163; -0.100] | True | False |

| Camada | Δ Macro-F1 (LLM − K-means) | Direção |
|---|---:|---|
| discovery | -0.136 | kmeans |
| final_request_types | -0.124 | kmeans |
| final_groups | -0.116 | kmeans |

### Sensibilidade descritiva da margem prática

A regra decisória permanece congelada em 0,03. Os demais limiares apenas mostram se a leitura depende dessa escolha.

| Margem | Direção principal | Direção igual nas 4 referências | IC inteiro na faixa de equivalência |
|---:|---|---|---|
| 0.02 | kmeans | True | False |
| 0.03 | kmeans | True | False |
| 0.05 | kmeans | True | False |

### Métricas secundárias da ablação

Dominância secundária: `kmeans`; conflito com a principal: `False`.

| Métrica | K-means | LLM | Margem | Direção material |
|---|---:|---:|---:|---|
| bcubed_f1 | 0.424 | 0.417 | 0.030 | equivalent |
| adjusted_rand_index | 0.282 | 0.238 | 0.030 | kmeans |
| adjusted_mutual_information | 0.531 | 0.403 | 0.030 | kmeans |
| minimum_reassignment_rate | 0.181 | 0.324 | 0.030 | kmeans |

### Estabilidade entre sementes

Cubo 3 seeds × 4 referências × 3 camadas completo: `True`.
Sensível à referência: `False`; à camada: `True`; à seed: `True`.

| Seed | Δ Macro-F1 (LLM − K-means) | Direção |
|---:|---:|---|
| 42 | -0.124 | kmeans |
| 27182 | -0.051 | kmeans |
| 31415 | +0.002 | equivalent |

Células cuja direção difere do recorte principal `consensus_full/final_request_types`:

| Seed | Referência | Camada | Δ | Direção |
|---:|---|---|---:|---|
| 27182 | consensus_strict | final_groups | -0.028 | equivalent |
| 27182 | consensus_full | final_groups | +0.003 | equivalent |
| 27182 | model_a | final_groups | +0.001 | equivalent |
| 27182 | model_b | final_groups | -0.020 | equivalent |
| 31415 | consensus_strict | final_request_types | -0.002 | equivalent |
| 31415 | consensus_strict | final_groups | -0.004 | equivalent |
| 31415 | consensus_full | final_request_types | +0.002 | equivalent |
| 31415 | consensus_full | final_groups | +0.011 | equivalent |
| 31415 | model_a | final_request_types | +0.002 | equivalent |
| 31415 | model_a | final_groups | +0.012 | equivalent |
| 31415 | model_b | final_request_types | -0.001 | equivalent |
| 31415 | model_b | final_groups | -0.009 | equivalent |

## Escopo e referência automática

- Universo antes do filtro estruturado: 1584
- Sala removida deterministicamente antes do Stage 1: 128
- Universo do Stage 2 congelado: 1456
- Exclusões adicionais dentro da análise: 0
- Casos indeterminados dentro da análise: 0
- Universo analítico: 1456
- Acordo estrito entre famílias de modelo: 1301 de 1456

As quatro visões (acordo estrito, cobertura total, modelo A e modelo B) precisam atingir a cobertura mínima e apontar na mesma direção para uma afirmação forte.

## Catálogo histórico do Jira como baseline descritivo

É o catálogo vigente na janela dos chamados, não o portfólio usado hoje. O rótulo histórico não entra na ablação; aparece apenas para mostrar se os métodos se aproximam mais do desenho adotado do que a estrutura anterior.

| Visão | N | Cobertura | Macro-F1 serviços | B-cubed F1 | ARI | Reatribuição mínima |
|---|---:|---:|---:|---:|---:|---:|
| consensus_full | 1456 | 100.0% | 0.398 | 0.327 | 0.153 | 46.1% |
| consensus_strict | 1301 | 89.4% | 0.393 | 0.353 | 0.162 | 42.7% |
| model_a | 1456 | 100.0% | 0.404 | 0.327 | 0.154 | 46.2% |
| model_b | 1456 | 100.0% | 0.377 | 0.332 | 0.140 | 44.0% |

## Aderência de todas as execuções — request types

| Execução | Família | Macro-F1 | B-cubed F1 | ARI | AMI | Reatribuição |
|---|---|---:|---:|---:|---:|---:|
| m1_legacy_llama | native | 0.354 | 0.534 | 0.333 | 0.366 | 43.2% |
| m2_native | native | 0.553 | 0.463 | 0.364 | 0.438 | 31.7% |
| llm_common_seed42 | ablation | 0.518 | 0.417 | 0.238 | 0.403 | 32.4% |
| kmeans_common_seed42 | ablation | 0.642 | 0.424 | 0.282 | 0.531 | 18.1% |
| llm_common_seed31415 | ablation_repeat | 0.556 | 0.497 | 0.334 | 0.504 | 25.1% |
| kmeans_common_seed31415 | ablation_repeat | 0.554 | 0.388 | 0.259 | 0.548 | 15.2% |
| llm_common_seed27182 | ablation_repeat | 0.560 | 0.512 | 0.441 | 0.477 | 30.0% |
| kmeans_common_seed27182 | ablation_repeat | 0.611 | 0.403 | 0.268 | 0.554 | 12.5% |

## Estabilidade alvo-independente entre réplicas

Este diagnóstico usa ARI apenas entre partições do mesmo método; não usa o portfólio curado e não entra na escolha do vencedor.

| Método | Camada | Pares | ARI mínimo | ARI mediano |
|---|---|---:|---:|---:|
| kmeans | discovery | 3 | 0.549 | 0.554 |
| kmeans | final_request_types | 3 | 0.486 | 0.519 |
| kmeans | final_groups | 3 | 0.628 | 0.658 |
| llm | discovery | 3 | 0.640 | 0.644 |
| llm | final_request_types | 3 | 0.312 | 0.379 |
| llm | final_groups | 3 | 0.380 | 0.433 |

## Serviços estratégicos na ablação

Células estratégicas avaliadas no cubo: 12 de 12; proteção aprovada: `True`; células/serviços não avaliáveis: 0.

| Serviço | Suporte | Avaliável | F1 K-means | F1 LLM | Vencedor − outro (principal) | Pior vencedor − outro no cubo |
|---|---:|---|---:|---:|---:|---:|
| HPC e Processamento de Alto Desempenho (GPU) | 98 | True | 0.835 | 0.481 | +0.354 | +0.223 |
| Máquinas Virtuais Individuais (Portal do Pesquisador) | 114 | True | 0.810 | 0.403 | +0.407 | +0.215 |
| Submissão do Plano de Gestão de Dados (PGD) de Pesquisa | 52 | True | 0.932 | 0.872 | +0.060 | -0.048 |
| Solicitação de Acesso a Bases de Dados | 87 | True | 0.439 | 0.245 | +0.194 | +0.018 |

## Custos comparáveis

O desempate usa somente o tempo da última execução bem-sucedida de todos os Stages 3–6. O consumo total de tentativas, tokens e GPU é publicado separadamente, sem escore composto. `canonicalize_stage3` integra o custo do Stage 3 nos braços comuns.

| Execução | Parede 3–6 | Consumo tentado | Tokens | GPU média / p95 | VRAM pico | Energia estimada |
|---|---:|---:|---:|---:|---:|---:|
| m1_legacy_llama | 2.01 h | 2.01 h | 1,018,166 (3/4 stages) | 88.9% / 100.0% | 59.8 GiB | 559.5 Wh |
| m2_native | 4.60 h | 4.60 h | 10,064,861 (4/4 stages) | 95.5% / 99.0% | 59.8 GiB | 1344.2 Wh |
| llm_common_seed42 | 4.41 h | 4.41 h | 8,684,298 (4/4 stages) | 95.8% / 99.0% | 59.8 GiB | 1292.5 Wh |
| kmeans_common_seed42 | 1.57 h | 1.57 h | 3,427,791 (4/4 stages) | 93.4% / 100.0% | 59.8 GiB | 454.7 Wh |
| llm_common_seed31415 | 4.43 h | 4.43 h | 8,980,503 (4/4 stages) | 95.9% / 99.0% | 59.8 GiB | 1302.7 Wh |
| kmeans_common_seed31415 | 1.69 h | 1.69 h | 4,099,262 (4/4 stages) | 93.1% / 100.0% | 59.8 GiB | 490.5 Wh |
| llm_common_seed27182 | 4.36 h | 4.36 h | 8,567,632 (4/4 stages) | 95.9% / 99.0% | 59.8 GiB | 1278.4 Wh |
| kmeans_common_seed27182 | 1.72 h | 1.72 h | 4,188,783 (4/4 stages) | 93.8% / 100.0% | 59.8 GiB | 495.9 Wh |

Resumo do gate de custo (diferença material mínima: 10%):

| Estimando | Esquerda | Direita | Gap | Vencedor |
|---|---:|---:|---:|---|
| Benchmark downstream | 2.01 h | 4.60 h | 56.3% | m1 |
| Ablação justa (medianas) | 1.69 h | 4.41 h | 61.6% | kmeans |

## Leitura correta

- O benchmark compara as arquiteturas downstream nos Stages 3–6 sobre o mesmo Stage 2. O M1 legado foi reexecutado com Llama e não é a resultados históricos; uma única execução não estima sua variância.
- Macro-F1, B-cubed, ARI, AMI e reatribuição respondem perguntas diferentes; nenhuma delas é convertida em nota circular.
- A referência automática mede estabilidade de projeção no alvo curado, não verdade objetiva nem validação externa independente.
- O relatório separado de campos confronta automaticamente o que os usuários fornecem ou omitem com os campos do portfólio final.
- O portfólio curado e seus campos continuam sendo a decisão estratégica adotada, qualquer que seja o vencedor metodológico.
