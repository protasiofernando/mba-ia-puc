# Resultados do Estudo Comparativo de Métodos de Descoberta

Este documento apresenta o resultado formal do estudo comparativo. Ele separa
deliberadamente **medição** (o que foi observado) de **conclusão** (o que as
regras pré-registradas permitem afirmar).

A separação existe porque, neste estudo, as duas coisas não coincidem. A
medição aponta de forma consistente para um dos métodos, e as regras, aplicadas
à mesma medição, recusam declará-lo vencedor. Ler as duas partes como se fossem
uma só produz exatamente a afirmação que o protocolo proíbe.

O estudo não escolhe sozinho o portfólio operacional. O portfólio curado foi
adotado pela gestão após examinar as recomendações automáticas e aplicar
critérios estratégicos de responsabilidade, navegação e visibilidade. A
comparação mede como diferentes métodos projetam os chamados nesse alvo; ela
não transforma o alvo em verdade externa por chamado.

## 1. Validade do resultado

O pacote final publicável foi validado antes desta síntese:

| Gate | Resultado |
|---|---:|
| Universo original | 1.584 chamados |
| Remoção estruturada do request type legado homônimo | 128 chamados |
| Universo analítico | 1.456 chamados |
| Exclusões adicionais dentro da análise | 0 |
| Casos indeterminados dentro da análise | 0 |
| Validação do resultado | `PASS` |
| Checks finais | 302 |
| Falhas | 0 |
| Visões de referência | 4 completas |
| Cubo controlado | 3 sementes × 4 referências × 3 camadas completo |

Os 128 registros removidos tinham todos o valor estruturado legado
`Solicitação de Acesso a Bases de Dados` em `Customer Request Type`. No contexto
institucional, esse rótulo pertencia ao fluxo de dados confidenciais/Sala de
Sigilo, atendido fora da DTI Pesquisa pela equipe de Banco de Dados; os outros
seis rótulos da política de exclusão tiveram
zero ocorrências no período. A exclusão ocorreu antes do Estágio 1, sem LLM e
sem leitura de texto livre. O serviço curado de mesmo nome é distinto: atende
acesso comum a pastas e bases de pesquisa fora da Sala de Sigilo. Sala permanece
visível no portal como encaminhamento para a Equipe de Segurança da Informação,
mas não participa de descoberta, métricas ou ranking.

As quatro visões automáticas de referência foram: consenso estrito, consenso
pleno, modelo A e modelo B. O consenso estrito cobriu 1.301 de 1.456 chamados;
as outras três visões cobriram todo o universo analítico.

## 2. O que foi comparado

O estudo responde a dois estimandos diferentes:

1. **Comparação de Arquiteturas:** compara uma execução completa do Método
   Estatístico e do Método Agêntico nos Estágios 3–6. É descritiva, pois vários
   componentes mudam simultaneamente.
2. **Comparação Controlada do Motor de Descoberta:** mantém insumo, interface e
   Estágios 4–6 iguais e troca somente o motor do Estágio 3: K-means ou LLM.
   Foi repetida com as sementes 42, 31.415 e 27.182.

A métrica primária pré-registrada foi o Macro-F1 por serviço na camada de
request types finais. A margem de relevância prática foi 0,03. B-cubed F1,
ARI, AMI e taxa mínima de reatribuição foram métricas secundárias, sem escore
composto. O custo foi analisado separadamente. O Macro-F1 dá o mesmo peso aos
sete serviços substantivos e exclui a categoria residual; cada serviço usa seu melhor
grupo predito de forma independente. Pareamento húngaro e diagnósticos de
fusão/fragmentação complementam essa escolha permissiva.

# Parte I: medição

## 3. Comparação de Arquiteturas

Valores positivos favorecem o Método Agêntico; valores negativos favorecem o
Método Estatístico.

| Visão | Descoberta | Request types finais | Grupos finais |
|---|---:|---:|---:|
| Consenso estrito | -0,092 | +0,202 | +0,107 |
| Consenso pleno | -0,060 | +0,199 | +0,090 |
| Modelo A | -0,068 | +0,186 | +0,070 |
| Modelo B | -0,091 | +0,190 | +0,070 |

Na visão primária (consenso pleno), o Método Agêntico ganhou **0,198** de
Macro-F1 nos request types finais, com IC bootstrap de 95% **[0,174; 0,224]**.
Os quatro intervalos por referência excluíram zero. Entretanto, a direção se
inverteu entre a descoberta e as camadas finais.

Essa inversão demonstra que o processamento downstream influencia
materialmente a qualidade final. Ela **não identifica o Estágio 5 como causa**:
rotulação, consolidação e classificação mudam conjuntamente no benchmark.
Seria necessária uma ablação específica do Estágio 5 para atribuir o ganho a
ele isoladamente.

## 4. Comparação Controlada do Motor de Descoberta

Na semente principal (42), valores negativos de Δ indicam vantagem do K-means.

| Visão da referência | Cobertura | Δ Macro-F1 (LLM − K-means) | IC 95% | Direção |
|---|---:|---:|---|---|
| Consenso estrito | 89,4% | -0,134 | [-0,167; -0,101] | K-means |
| Consenso pleno | 100,0% | -0,124 | [-0,155; -0,095] | K-means |
| Modelo A | 100,0% | -0,117 | [-0,147; -0,086] | K-means |
| Modelo B | 100,0% | -0,129 | [-0,163; -0,100] | K-means |

A direção também foi K-means nas três camadas do recorte principal:

| Camada | Δ Macro-F1 (LLM − K-means) |
|---|---:|
| Descoberta | -0,136 |
| Request types finais | -0,124 |
| Grupos finais | -0,116 |

A leitura não dependeu de escolher margem prática 0,02, 0,03 ou 0,05 no
recorte principal. As métricas secundárias também favoreceram K-means: houve
vantagem material em ARI, AMI e menor reatribuição, equivalência em B-cubed e
nenhuma perda material.

| Métrica secundária | K-means | LLM | Leitura material |
|---|---:|---:|---|
| B-cubed F1 | 0,424 | 0,417 | equivalente |
| ARI | 0,282 | 0,238 | K-means |
| AMI | 0,531 | 0,403 | K-means |
| Reatribuição mínima | 18,1% | 32,4% | K-means |

### 4.1 Sensibilidade entre sementes

| Seed | Δ Macro-F1 (LLM − K-means) | Direção |
|---:|---:|---|
| 42 | -0,124 | K-means |
| 27.182 | -0,051 | K-means |
| 31.415 | +0,002 | equivalentes |

Portanto, a vantagem observada do K-means não foi uniforme: permaneceu nas
sementes 42 e 27.182, mas desapareceu na semente 31.415. Também houve células
equivalentes em grupos finais com as sementes 27.182 e 31.415. Esse é o motivo pelo
qual a regra pré-registrada não autoriza declarar vencedor global de
aderência.

### 4.2 Estabilidade alvo-independente

O ARI entre réplicas do mesmo método, sem usar o portfólio curado, mostrou:

| Método | Camada | ARI mínimo | ARI mediano |
|---|---|---:|---:|
| K-means | Descoberta | 0,549 | 0,554 |
| K-means | Request types finais | 0,486 | 0,519 |
| K-means | Grupos finais | 0,628 | 0,658 |
| LLM | Descoberta | 0,640 | 0,644 |
| LLM | Request types finais | 0,312 | 0,379 |
| LLM | Grupos finais | 0,380 | 0,433 |

A LLM foi mais estável na partição bruta de descoberta, enquanto K-means foi
mais estável nas saídas consolidadas. Isso reforça que motor e processamento
downstream interagem; não sustenta atribuição isolada ao Estágio 5.

## 5. Serviços estratégicos

Os quatro serviços protegidos foram avaliáveis em todas as 12 células do cubo.
O critério de proteção dos serviços estratégicos foi atendido: nenhuma perda
excedeu o limite pré-registrado de
0,10.

| Serviço | F1 K-means | F1 LLM | Margem principal | Pior margem do vencedor no cubo |
|---|---:|---:|---:|---:|
| HPC e Processamento de Alto Desempenho | 0,835 | 0,481 | +0,354 | +0,223 |
| Máquinas Virtuais Individuais | 0,810 | 0,403 | +0,407 | +0,215 |
| Plano de Gestão de Dados | 0,932 | 0,872 | +0,060 | -0,048 |
| Acesso a Bases de Dados | 0,439 | 0,245 | +0,194 | +0,018 |

## 6. Custo

O custo comparável usa o tempo da última execução bem-sucedida dos Estágios
3–6. Tokens, GPU e energia permanecem dimensões separadas.

| Estimando | Método Estatístico | Método Agêntico | Redução estatística |
|---|---:|---:|---:|
| Arquiteturas completas | 2,01 h | 4,60 h | 56,3% |
| Motores, mediana de 3 sementes | 1,69 h | 4,41 h | 61,6% |

Nos braços controlados, as execuções K-means consumiram entre 3,43 e 4,19
milhões de tokens e aproximadamente 455–496 Wh; as execuções LLM consumiram
entre 8,57 e 8,98 milhões de tokens e aproximadamente 1.278–1.303 Wh. Ambos os
pipelines ainda usam LLM nos estágios comuns, portanto “estatístico” descreve o
motor de descoberta, não ausência total de LLM.

# Parte II: conclusão

## 7. Conclusões permitidas pelas regras pré-registradas

| Escopo | Código formal | Interpretação |
|---|---|---|
| Arquiteturas completas | `operacional_inconclusivo_dependente_da_camada` | A arquitetura agêntica foi melhor na saída final, mas pior na descoberta; uma execução não isola a causa nem estima variância. |
| Motor de descoberta | `inconclusivo_dependente_da_camada` | O recorte principal e duas sementes favoreceram K-means, mas a semente 31.415 e células de camada produziram equivalência. |
| Resultado integrado | `resultado_global_nao_unico` | Os estimandos respondem perguntas diferentes e não autorizam um vencedor global de aderência. |
| Custo | `custo_convergente_estatistico` | Os dois estimandos apontaram menor tempo e consumo para o caminho estatístico. |

Em linguagem executiva: **há evidência relevante favorável ao K-means como
motor de descoberta, mas não há vencedor formal de aderência** devido à
sensibilidade à semente e à camada. A única conclusão convergente e forte entre os
dois estimandos é a de eficiência: o caminho estatístico foi substancialmente
mais barato.

Não é defensável afirmar que “a vantagem do Método Agêntico vem do Estágio 5”.
O estudo demonstra que a diferença aparece depois da descoberta no benchmark,
mas não separa causalmente os Estágios 4, 5 e 6.

## 8. Resposta aplicada: portfólio adotado

O resultado operacional permanece o portfólio curado: **sete serviços
analíticos, uma categoria residual e Sala de Sigilo como encaminhamento fixo**.
Essa decisão combina evidência automática e curadoria estratégica; não depende
de declarar um método vencedor.

Sua precedência é auditável: um pipeline estatístico com `bge-m3` + K-means
formou o candidato inicial; a área o curou no nível do catálogo e congelou
`formacao_portfolio/decisao_curada/feedback_portfolio.json`; somente depois os
dois métodos foram reexecutados no
estudo. Portanto, estes resultados comparam quanto cada método reconstrói a
decisão adotada. Eles não foram usados para criar retroativamente o alvo.

O registro público de 3 de julho contém a recomendação automática de dez itens,
a curadoria para sete e sua materialização pelo Estágio 7. O desenho atual evoluiu
com Acesso a Bases e Sala de Sigilo como encaminhamento fixo. Essa evolução é
gerencial e antecede o alvo congelado usado no experimento.

| Grupo | Serviço | Informações solicitadas ao usuário |
|---|---|---|
| Infraestrutura Computacional | Servidores Acadêmicos Compartilhados | usuários; projeto/pesquisa; classificação dos dados; servidor existente; descrição da necessidade |
| Softwares e Licenças | Softwares e Licenças Acadêmicas | nome e versão; tipo de demanda; ambiente; usuários; finalidade acadêmica |
| Nuvem Pública | Nuvem Pública (AWS, Azure, GCP) | provedor; SI/orçamento/centro de custo; recursos; usuários; prazo de uso |
| Infraestrutura Computacional | HPC e Processamento de Alto Desempenho (GPU) | finalidade; recurso computacional; usuários; acesso externo/VPN; dimensão da carga |
| Infraestrutura Computacional | Máquinas Virtuais Individuais | sistema operacional; vCPU/RAM/disco; finalidade; responsável; prazo |
| Dados e Governança | Submissão do Plano de Gestão de Dados | projeto; pesquisador; fomento; prazo; classificação dos dados |
| Dados e Governança | Solicitação de Acesso a Bases de Dados | base/repositório; tipo de demanda; usuários; projeto/finalidade; permissão e prazo |
| Triagem | Não encontrou o que procurava? | descrição detalhada; sistema/recurso; impacto/urgência; área relacionada |
| Encaminhamento | Sala de Sigilo | formulário gerido pela Equipe de Segurança da Informação; item visível, imutável e fora da análise |

O confronto automático com o histórico ajuda a priorizar os campos, mas não os
define sozinho. Os maiores sinais de informação faltante foram: descrição no
categoria residual (53,8%), permissão e prazo em acesso a bases (30,2%), descrição em
servidores compartilhados (23,2%), perfil de VM (22,4%), usuários em acesso a
bases (18,6%) e usuários na nuvem (12,8%). Essas taxas são retrospectivas e
dependem do alinhamento semântico automático; os campos finais são uma decisão
curada.

Após o encerramento do estudo, o Estágio 7 vigente projetou automaticamente os
1.456 chamados no portfólio adotado. O agregado resultou em 455 chamados em
Servidores Acadêmicos, 426 em Nuvem Pública, 246 em Softwares e Licenças, 98
em Máquinas Virtuais, 95 em HPC, 65 em Acesso a Bases, 48 em PGD e 23 no
categoria residual. Essa materialização é uma saída operacional posterior: não entrou
nas métricas do Job 90, não altera a comparação e não equivale a uso observado
depois da implantação do novo portal.

## 9. Limitações

- A referência por chamado é automática (Llama + Qwen), não uma classificação
  humana independente.
- O candidato do Método Estatístico informou a curadoria; logo, o alvo é
  endógeno ao processo de projeto e não uma referência externa independente. A
  reexecução posterior dos dois braços evita circularidade direta, mas não
  elimina essa limitação de origem.
- A inferência é retrospectiva e in-sample; o bootstrap é condicional ao corpus
  e não prova generalização temporal ou populacional.
- O benchmark de arquiteturas tem uma execução por arquitetura e não isola qual
  estágio downstream explica a diferença.
- A comparação controlada tem três sementes; a variação observada foi suficiente para impedir um
  vencedor formal de aderência.
- As taxas de campos usam alinhamento `bge-m3` com limiar principal 0,55 e devem
  ser interpretadas como evidência de apoio, não julgamento do usuário.
- O portfólio curado é um alvo operacional definido após a formação do
  candidato, não uma referência externa independente.
- O repositório público reúne regras e resultados no mesmo commit-raiz; hashes,
  manifestos e timestamps preservam proveniência interna, mas não comprovam de
  forma independente a anterioridade temporal do pré-registro.

## 10. Proveniência

| Artefato | SHA-256 |
|---|---|
| Pacote executável | `a2896c3e46f0b8d6dc90660a8715bf719effcfd55af4964e3486cb9283b1967c` |
| Pacote público final | `f476e4103044ee0cc578597523689cbafaf7b2b164fa720a5078808bc4545be6` |
| Pacote privado final | `a8c66f9a1923c98a5756566040b1b8f216c586d46ed9f3d3a933641e741053eb` |
| Métricas comparativas | `2ec80b28fe8db496154adb722b3ff8cf8b6de70c4f5dadbbfe9667858930a798` |
| Validação final | `fd0c98e51b6330a7b5d42a0c92b517c2dc729b1d83acff2ae15bbe6f5f3b565a` |

O avaliador final foi executado pelo Job PBS `2234.HPCGPU`
(`cmp_evaluate`) no workspace `/u00/fernando.protasio/mba-ia-puc_rev6`.
Terminou em `F/Exit_status=0`, com walltime `00:01:04`, às 13:11:23 de
04/08/2026. O log encerrou com `failures=0` e registrou os caminhos dos pacotes
público e privado.

O pacote público contém somente configuração, proveniência, métricas agregadas,
relatórios e validações. A varredura local não encontrou chaves Jira, texto ou
classificações por chamado. O pacote privado permanece em `_hpc/` e não deve
ser versionado ou enviado a serviços externos.
