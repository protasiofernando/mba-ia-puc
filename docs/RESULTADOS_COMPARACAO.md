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
request types finais. B-cubed F1, ARI, AMI e taxa mínima de reatribuição foram
métricas secundárias. O custo foi analisado separadamente, sem transformar
qualidade e custo em uma nota composta.

### 2.1 Unidade de análise, camadas e referência

A unidade de análise é o chamado. Para cada um dos 1.456 chamados, cada método
produziu um rótulo em três camadas:

- **descoberta:** grupo produzido diretamente pelo motor do Estágio 3;
- **request type final:** serviço obtido depois da rotulação, consolidação e
  classificação dos Estágios 4–6;
- **grupo final:** agrupador lógico mais amplo ao qual o serviço pertence.

Esses rótulos foram confrontados com uma projeção automática dos chamados no
portfólio curado. O consenso estrito inclui somente o acordo inicial entre
Llama e Qwen sem baixa confiança ou ambiguidade. O consenso pleno resolve os
demais casos por maioria dos quatro votos ou por desempate automático. As
visões Modelo A e Modelo B preservam separadamente os votos iniciais de cada
modelo. Assim, **cobertura** é `número de chamados avaliáveis / 1.456`: 1.301
chamados correspondem a 89,4% no consenso estrito, enquanto as outras visões
cobrem 100%.

O estudo mede, portanto, **aderência a essa referência automática e ao
portfólio adotado**. Não mede acurácia contra uma verdade humana independente.

### 2.2 Notação comum aos cálculos

As métricas partem de uma tabela de contingência que cruza o grupo produzido
pelo método com o serviço de referência. Nesta seção:

- `N` é o número de chamados avaliáveis;
- `nᵢⱼ` é o número de chamados simultaneamente no grupo predito `i` e no
  serviço de referência `j`;
- `aᵢ = Σⱼ nᵢⱼ` é o tamanho do grupo predito `i`;
- `bⱼ = Σᵢ nᵢⱼ` é o número de chamados do serviço de referência `j`;
- `C(x,2) = x(x−1)/2` é o número de pares que podem ser formados com `x`
  chamados.

| Medida | Pergunta respondida | Direção desejável |
|---|---|---|
| Macro-F1 por serviço | Cada serviço do portfólio foi recuperado com precisão e cobertura? | maior |
| B-cubed F1 | Os chamados que deveriam estar juntos ou separados receberam grupos coerentes? | maior |
| ARI | As duas partições concordam além do que seria esperado ao acaso? | maior |
| AMI | Quanta informação sobre uma partição é fornecida pela outra, descontado o acaso? | maior |
| Reatribuição mínima | Quantos chamados ainda precisariam mudar após renomear livremente os grupos? | menor |
| Δ Macro-F1 | Qual método teve maior Macro-F1 e por quanto? | sinal depende da ordem da subtração |

Não existe um corte universal que transforme, por exemplo, Macro-F1 0,60 em
“bom” ou “ruim”. Os valores são comparados entre métodos no mesmo corpus, na
mesma camada e diante da mesma visão de referência.

### 2.3 Macro-F1 por serviço e diferença entre métodos

Para cada par formado pelo grupo predito `i` e pelo serviço `j`, calculam-se:

```text
Precisãoᵢⱼ = nᵢⱼ / aᵢ
Revocaçãoᵢⱼ = nᵢⱼ / bⱼ
F1ᵢⱼ = 2 × Precisãoᵢⱼ × Revocaçãoᵢⱼ / (Precisãoᵢⱼ + Revocaçãoᵢⱼ)
       = 2 × nᵢⱼ / (aᵢ + bⱼ)
```

Para cada um dos sete serviços substantivos, o avaliador escolhe
independentemente o grupo predito com maior F1. A categoria residual não entra
na média:

```text
F1 do serviço j = máximoᵢ(F1ᵢⱼ)
Macro-F1 = (1/7) × Σⱼ F1 do serviço j
```

O Macro-F1 varia de 0 a 1. O valor 1 representa correspondência perfeita dos
sete serviços; valores maiores indicam maior aderência. Como cada serviço recebe
peso `1/7`, serviços de grande volume não apagam os menores. Como o melhor grupo
é escolhido separadamente para cada serviço, uma mesma categoria predita pode
ser o melhor par de mais de um serviço. Por isso, Macro-F1 não é o percentual
simples de chamados corretos e precisa ser lido junto com as métricas de
partição.

Na comparação controlada:

```text
Δ Macro-F1 = Macro-F1 do LLM − Macro-F1 do K-means
```

Na comparação de arquiteturas, a mesma lógica usa `Método Agêntico − Método
Estatístico`. Um Δ de `−0,124` significa que o primeiro termo da subtração ficou
0,124 abaixo do segundo: são 12,4 pontos na escala de 0 a 100 do Macro-F1, não
12,4% mais chamados corretos.

### 2.4 Métricas secundárias

**B-cubed F1.** A precisão B-cubed aumenta quando os chamados reunidos em cada
grupo pertencem ao mesmo serviço de referência; a revocação aumenta quando os
chamados de um serviço permanecem reunidos. O avaliador usa:

```text
Precisão B³ = (1/N) × Σᵢⱼ (nᵢⱼ² / aᵢ)
Revocação B³ = (1/N) × Σᵢⱼ (nᵢⱼ² / bⱼ)
B³ F1 = 2 × Precisão B³ × Revocação B³ /
        (Precisão B³ + Revocação B³)
```

O resultado varia de 0 a 1 e valores maiores são melhores. Diferentemente do
Macro-F1, cada chamado participa da média e não se escolhe um melhor grupo
independentemente para cada serviço.

**ARI — índice de Rand ajustado.** O ARI examina todos os pares de chamados e
verifica se as duas partições concordam em mantê-los juntos ou separados. A
correção desconta a concordância que apareceria ao acaso. Definindo
`S = Σᵢⱼ C(nᵢⱼ,2)`, `A = Σᵢ C(aᵢ,2)`, `B = Σⱼ C(bⱼ,2)` e `T = C(N,2)`:

```text
ARI = [S − (A × B / T)] /
      [0,5 × (A + B) − (A × B / T)]
```

ARI igual a 1 indica partições idênticas; valor próximo de 0 indica concordância
compatível com o acaso, e valores negativos indicam concordância inferior à
esperada ao acaso. O ARI não depende dos nomes dados aos grupos.

**AMI — informação mútua ajustada.** A informação mútua mede quanto conhecer o
grupo em uma partição reduz a incerteza sobre o grupo na outra. O ajuste remove
a parcela esperada ao acaso:

```text
MI = Σᵢⱼ (nᵢⱼ/N) × ln[(N × nᵢⱼ)/(aᵢ × bⱼ)]
AMI = [MI − E(MI)] /
      [0,5 × (H da predição + H da referência) − E(MI)]
```

`H` representa a entropia da partição e `E(MI)` a informação mútua esperada ao
acaso para partições com esses tamanhos. AMI igual a 1 indica concordância
perfeita; valor próximo de 0 indica informação compartilhada compatível com o
acaso, podendo ocorrer valor negativo.

**Taxa mínima de reatribuição.** Cada grupo predito é renomeado livremente como
o serviço de referência mais frequente dentro dele. Depois dessa renomeação
muitos-para-um, conta-se a menor fração que ainda precisaria trocar de grupo:

```text
Reatribuição mínima = 1 − [Σᵢ máximoⱼ(nᵢⱼ) / N]
```

Valor 0 significa que nenhum chamado precisaria mudar depois da renomeação;
valores menores são melhores. Essa medida não impõe correspondência
biunívoca. O **pareamento húngaro**, publicado como diagnóstico complementar,
faz justamente o alinhamento um-para-um que maximiza a sobreposição e ajuda a
detectar fusões ou fragmentações ocultadas pelo melhor par independente.

### 2.5 Intervalo de confiança bootstrap e regra de leitura

O intervalo de confiança (IC) de 95% quantifica quanto o Δ varia quando o mesmo
corpus é reamostrado. O procedimento foi um bootstrap não paramétrico pareado:

1. sorteiam-se `N` posições entre os `N` chamados, com reposição;
2. usa-se a mesma amostra para K-means, LLM e referência, preservando o pareamento;
3. recalculam-se os dois Macro-F1 e o Δ;
4. repetem-se os passos anteriores 2.000 vezes;
5. os percentis 2,5% e 97,5% dos 2.000 deltas formam o IC de 95%.

Por exemplo, `IC 95% [-0,155; -0,095]` significa que o intervalo central dos
deltas reamostrados ficou abaixo de zero e, portanto, manteve a direção
favorável ao K-means naquele recorte. O IC é condicional aos 1.456 chamados
observados: ele não demonstra generalização para outros períodos ou populações.

A margem de relevância prática foi congelada em 0,03. Para uma célula:

- `Δ < −0,03`: direção material K-means;
- `−0,03 ≤ Δ ≤ +0,03`: equivalência prática descritiva;
- `Δ > +0,03`: direção material LLM.

Uma declaração formal de equivalência é mais exigente: os quatro intervalos de
confiança precisam estar inteiramente contidos em `[-0,03; +0,03]`, além dos
demais gates previstos. Assim, um Δ pontual dentro da margem em uma semente não
prova equivalência global.

### 2.6 Robustez, serviços estratégicos e custo

A sensibilidade a sementes verifica se a direção muda quando componentes
pseudoaleatórios recebem inicializações diferentes. A estabilidade
alvo-independente usa o ARI diretamente entre pares de execuções do mesmo
método, sem consultar o portfólio curado. Com três sementes existem três pares;
o ARI mínimo representa o pior par e o mediano, o par central.

Nos serviços estratégicos, o F1 individual usa a mesma fórmula da seção 2.3.
Cada serviço precisa ter pelo menos cinco chamados. A margem é `F1 K-means − F1
LLM`, e a pior margem é o menor valor observado nas 12 combinações de três
sementes por quatro referências. Uma perda maior que 0,10 impediria uma
conclusão forte favorável ao método vencedor.

O custo comparável é a soma dos tempos da última execução bem-sucedida dos
Estágios 3–6. Na comparação controlada usa-se a mediana das três sementes. A
redução atribuída ao caminho estatístico é:

```text
Redução = 100 × (tempo agêntico − tempo estatístico) / tempo agêntico
```

Tokens e energia são telemetrias separadas: tokens correspondem à soma dos
tokens de entrada e saída registrados nas chamadas; a energia em Wh é estimada
pela integração trapezoidal da potência da GPU ao longo das janelas medidas:

```text
Energia ≈ Σₜ [(potênciaₜ + potênciaₜ₊₁)/2] × Δtempoₜ / 3.600
```

Essas dimensões não são combinadas com aderência em um escore único. As
fórmulas acima correspondem à implementação do avaliador final em
[`scripts/avaliar_comparacao_robusta.py`](../scripts/avaliar_comparacao_robusta.py)
e às regras congeladas em
[`estudo_comparativo/decision_rules_v1.json`](../estudo_comparativo/decision_rules_v1.json).

# Parte I: medição

## 3. Comparação de Arquiteturas

Cada célula da tabela é `Δ Macro-F1 = Método Agêntico − Método Estatístico`, e
não o Macro-F1 absoluto de um método. Valores positivos favorecem o Método
Agêntico; valores negativos favorecem o Método Estatístico.

| Visão | Δ na descoberta | Δ nos request types finais | Δ nos grupos finais |
|---|---:|---:|---:|
| Consenso estrito | -0,092 | +0,202 | +0,107 |
| Consenso pleno | -0,060 | +0,199 | +0,090 |
| Modelo A | -0,068 | +0,186 | +0,070 |
| Modelo B | -0,091 | +0,190 | +0,070 |

Na visão primária (consenso pleno), os Macro-F1 observados nos request types
finais foram **0,354** para o Método Estatístico e **0,553** para o Método
Agêntico, diferença observada de **+0,199**. Nas 2.000 reamostragens, a diferença
média foi **+0,198**, com IC bootstrap de 95% **[+0,174; +0,224]**. Os quatro
intervalos por referência excluíram zero. Entretanto, a direção se inverteu
entre a descoberta e as camadas finais.

Essa inversão demonstra que o processamento downstream influencia
materialmente a qualidade final. Ela **não identifica o Estágio 5 como causa**:
rotulação, consolidação e classificação mudam conjuntamente no benchmark.
Seria necessária uma ablação específica do Estágio 5 para atribuir o ganho a
ele isoladamente.

## 4. Comparação Controlada do Motor de Descoberta

O símbolo Δ representa `Macro-F1 do LLM − Macro-F1 do K-means`. Valores
negativos indicam que o K-means obteve o maior resultado; valores positivos
indicam LLM. A diferença é medida na escala de 0 a 1: por exemplo, -0,124
corresponde a 12,4 pontos de Macro-F1 a favor do K-means, não a 12,4% mais
chamados corretos. A margem prática pré-registrada foi 0,03.

| Visão da referência | Cobertura | Macro-F1 K-means | Macro-F1 LLM | Δ (LLM − K-means) | IC 95% do Δ | Direção |
|---|---:|---:|---:|---:|---|---|
| Consenso estrito | 89,4% | 0,662 | 0,528 | -0,134 | [-0,167; -0,101] | K-means |
| Consenso pleno | 100,0% | 0,642 | 0,518 | -0,124 | [-0,155; -0,095] | K-means |
| Modelo A | 100,0% | 0,626 | 0,508 | -0,117 | [-0,147; -0,086] | K-means |
| Modelo B | 100,0% | 0,647 | 0,519 | -0,129 | [-0,163; -0,100] | K-means |

A direção também foi K-means nas três camadas do recorte principal:

| Camada | Macro-F1 K-means | Macro-F1 LLM | Δ (LLM − K-means) |
|---|---:|---:|---:|
| Descoberta | 0,534 | 0,398 | -0,136 |
| Request types finais | 0,642 | 0,518 | -0,124 |
| Grupos finais | 0,754 | 0,638 | -0,116 |

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

O B-cubed F1 avalia por chamado a pureza e a cobertura dos grupos. O ARI mede a
concordância global entre pares de chamados, corrigida pelo acaso, e o AMI mede
a informação compartilhada entre as partições, também corrigida pelo acaso;
nessas três métricas, valores maiores são melhores. A reatribuição mínima é a
menor parcela de chamados que precisaria mudar depois de cada grupo predito ser
renomeado como seu serviço de referência mais frequente; portanto, valores
menores são melhores.

Nos resultados, a diferença de B-cubed foi `0,424 − 0,417 = 0,007`, abaixo da
margem de 0,03 e, por isso, materialmente equivalente. O K-means superou o LLM
em 0,044 de ARI e 0,128 de AMI, ambos acima da margem. Na reatribuição, o K-means
exigiu 18,1% contra 32,4% do LLM, diferença favorável de 14,3 pontos
percentuais. Essas três vantagens materiais e a ausência de perda secundária
sustentam a direção secundária K-means, sem substituir a métrica primária.

### 4.1 Sensibilidade entre sementes

Uma semente é o número usado para inicializar componentes pseudoaleatórios. O
mesmo valor foi aplicado aos dois métodos em cada par, permitindo observar se a
conclusão dependia da inicialização. Nesta tabela, “equivalentes” significa que
a diferença daquela semente ficou dentro da margem prática de ±0,03; não é uma
declaração de equivalência global entre os métodos.

| Semente | Macro-F1 K-means | Macro-F1 LLM | Δ (LLM − K-means) | Direção pela margem de 0,03 |
|---:|---:|---:|---:|---|
| 42 | 0,642 | 0,518 | -0,124 | K-means |
| 27.182 | 0,611 | 0,560 | -0,051 | K-means |
| 31.415 | 0,554 | 0,556 | +0,002 | equivalentes |

Portanto, a vantagem observada do K-means não foi uniforme: permaneceu nas
sementes 42 e 27.182, mas desapareceu na semente 31.415. Também houve células
equivalentes em grupos finais com as sementes 27.182 e 31.415. Esse é o motivo pelo
qual a regra pré-registrada não autoriza declarar vencedor global de
aderência.

### 4.2 Estabilidade alvo-independente

O ARI entre réplicas do mesmo método compara diretamente as partições das três
sementes, sem usar o portfólio curado. Para cada método e camada foram calculados
os três pares possíveis entre as sementes; a tabela apresenta o pior valor e a
mediana desses três ARIs:

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
O critério de proteção dos serviços estratégicos foi atendido: todos tiveram
suporte mínimo de cinco chamados e nenhuma perda excedeu o limite
pré-registrado de 0,10. Como a direção principal foi K-means, as margens abaixo
são `F1 K-means − F1 LLM`. Valor positivo favorece K-means; valor negativo
indica que o LLM foi melhor naquela célula.

| Serviço | F1 K-means | F1 LLM | Margem principal (K − LLM) | Menor margem no cubo (K − LLM) |
|---|---:|---:|---:|---:|
| HPC e Processamento de Alto Desempenho | 0,835 | 0,481 | +0,354 | +0,223 |
| Máquinas Virtuais Individuais | 0,810 | 0,403 | +0,407 | +0,215 |
| Plano de Gestão de Dados | 0,932 | 0,872 | +0,060 | -0,048 |
| Acesso a Bases de Dados | 0,439 | 0,245 | +0,194 | +0,018 |

Por exemplo, o Plano de Gestão de Dados favoreceu K-means em 0,060 no recorte
principal, mas sua menor margem no cubo foi −0,048: em pelo menos uma combinação
de semente e referência, o LLM ficou 0,048 acima. Essa perda permaneceu menor
que o limite tolerado de 0,10.

## 6. Custo

O custo comparável usa o tempo da última execução bem-sucedida dos Estágios
3–6. Nas arquiteturas completas há uma execução de cada método; nos motores,
comparam-se as medianas das três sementes. Tokens, GPU e energia permanecem
dimensões separadas.

| Estimando | Método Estatístico | Método Agêntico | Redução estatística |
|---|---:|---:|---:|
| Arquiteturas completas | 2,01 h | 4,60 h | 56,3% |
| Motores, mediana de 3 sementes | 1,69 h | 4,41 h | 61,6% |

Na primeira linha, por exemplo, `(4,60 − 2,01) / 4,60 = 56,3%`: o caminho
estatístico consumiu 56,3% menos tempo que o agêntico. A mesma fórmula aplicada
aos valores não arredondados das medianas produz 61,6% na comparação controlada.

Nos braços controlados, as execuções K-means consumiram entre 3,43 e 4,19
milhões de tokens e aproximadamente 455–496 Wh; as execuções LLM consumiram
entre 8,57 e 8,98 milhões de tokens e aproximadamente 1.278–1.303 Wh. Ambos os
pipelines ainda usam LLM nos estágios comuns, portanto “estatístico” descreve o
motor de descoberta, não ausência total de LLM. A energia é uma estimativa
obtida das amostras de potência da GPU nas janelas registradas dos Estágios 3–6;
não representa faturamento elétrico ou custo financeiro.

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
define sozinho. Os maiores sinais de informação faltante foram: descrição na
categoria residual (53,8%), permissão e prazo em acesso a bases (30,2%),
descrição em servidores compartilhados (23,2%), perfil de VM (22,4%), usuários
em acesso a bases (18,6%) e usuários na nuvem (12,8%). Essas taxas são
retrospectivas e dependem do alinhamento semântico automático; os campos finais
são uma decisão curada.

Após o encerramento do estudo, o Estágio 7 vigente projetou automaticamente os
1.456 chamados no portfólio adotado. O agregado resultou em 455 chamados em
Servidores Acadêmicos, 426 em Nuvem Pública, 246 em Softwares e Licenças, 98
em Máquinas Virtuais, 95 em HPC, 65 em Acesso a Bases, 48 em PGD e 23 na
categoria residual. Essa materialização é uma saída operacional posterior: não
entrou nas métricas do Job 90, não altera a comparação e não equivale a uso
observado depois da implantação do novo portal.

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

Os artefatos promovidos foram preservados byte a byte e, por isso, o relatório
automático mantém um parágrafo de abertura herdado que descreve o procedimento
de escopo da geração anterior, não o filtro determinístico que efetivamente
rodou. A discrepância, o procedimento canônico e a linha do próprio relatório
que o confirma estão reunidos na nota editorial de
[`resultados_publicaveis/README.md`](../resultados_publicaveis/README.md); a
justificativa para não reescrever o gerador está em
[`APENDICE_TECNICO.md`](APENDICE_TECNICO.md). Nenhuma métrica desta síntese
depende daquele parágrafo: todas foram calculadas sobre o universo determinístico
de 1.456 chamados.
