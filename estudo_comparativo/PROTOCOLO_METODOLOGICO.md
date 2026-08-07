# Protocolo metodológico pré-registrado — v6

> **Clarificação editorial pós-execução (07/08/2026).** O único request type
> que efetivamente casou com a política de exclusão foi o rótulo legado
> `Solicitação de Acesso a Bases de Dados` (128 registros), pertencente ao fluxo
> de dados confidenciais/Sala de Sigilo e atendido fora da DTI Pesquisa pela
> equipe de Banco de Dados. Ele é distinto do serviço curado homônimo para
> acesso comum fora da Sala. Esta nota
> corrige a descrição semântica do recorte; não altera regra, corpus, hashes,
> limiares ou resultados. Os bytes e hashes da execução permanecem preservados
> no pacote de proveniência.

## 1. Pergunta e estimando

O projeto busca o portfólio que melhor atende às demandas reais e as informações
que o usuário deve fornecer na abertura. O pipeline produz recomendações; a
decisão final é curada pela gestão à luz de responsabilidade técnica,
governança, visibilidade e operabilidade.

A comparação não tenta provar qual algoritmo descobre uma taxonomia verdadeira.
O estimando principal é:

> aderência retrospectiva, dentro deste corpus, entre a saída de cada método e
> o portfólio operacional curado ex post.

Não se afirma generalização temporal ou populacional.

## 2. Universo e Sala de Sigilo

O universo original tinha 1.584 chamados. Antes do Estágio 1 foram removidos 128
registros cujo campo estruturado `Customer Request Type` correspondia exatamente
ao rótulo legado `Solicitação de Acesso a Bases de Dados` do fluxo de dados
confidenciais/Sala de Sigilo, atendido fora da DTI Pesquisa pela equipe de Banco
de Dados. Os outros seis request types da lista de exclusão tiveram zero
ocorrências. Restaram 1.456 chamados. O serviço curado homônimo
cobre acesso comum a pastas e bases fora da Sala e não representa os registros
removidos.

Regras congeladas:

- decisão somente pelo campo estruturado;
- correspondência exata após `strip`, sensível a maiúsculas conforme manifesto;
- nenhum resumo, descrição ou comentário é lido para decidir escopo;
- nenhuma LLM decide escopo;
- o Estágio 2 v6 é regenerado do zero em diretório isolado;
- a máscara interna inclui os 1.456 registros, sem exclusão ou indeterminado;
- Sala continua visível no portfólio, mas fora de descoberta, métricas e ranking.

Os hashes por CSV e a lista de request types ficam em
`filtro_sala_sigilo_manifest_v6.json`. O Estágio 2 só será pré-registrado pelo seu
SHA-256 depois de concluído; o gerador do ZIP final recusa manifesto divergente.

O repositório público foi consolidado após a execução, com regras e resultados
no mesmo commit-raiz. Logo, ele preserva a proveniência interna deste protocolo,
mas não fornece comprovação temporal independente de sua anterioridade. Uma
replicação deve depositar as regras em serviço externo imutável antes da
liberação dos resultados.

## 3. Desenhos de comparação

### 3.1 Benchmark operacional

- `m1_legacy_llama`: arquitetura estatística legada mínima, reexecutada;
- `m2_native`: arquitetura LLM nativa.

O mesmo Estágio 2 e alvo são usados, mas mais de um componente downstream muda.
Logo, a conclusão é descritiva sobre arquiteturas, não causal sobre K-means
versus LLM.

### 3.2 Ablação comum

- `kmeans_common_seed42`;
- `llm_common_seed42`;
- repetições pareadas nas seeds `31415` e `27182`.

Nos braços comuns são congelados:

- registros e ordem;
- modelo de embedding e modelos semânticos;
- contratos de entrada/saída;
- normalização intermediária;
- Estágios 4, 5 e 6;
- portfólio-alvo;
- avaliador;
- hardware e telemetria.

A variável de interesse é o motor de descoberta no Estágio 3.

## 4. Referência automática e portfólio curado

Não há classificação manual por chamado. Llama e Qwen projetam cada demanda nas
categorias analíticas do portfólio curado, sem receber a chave Jira real nem a
categoria histórica. Os identificadores são opacos e há quatro visões:

- `consensus_strict`;
- `consensus_full`;
- `model_a`;
- `model_b`.

O protocolo de votação é:

1. `a1`: Llama avalia todos os 1.456 registros com categorias em ordem normal;
2. `b1`: Qwen avalia todos os 1.456 com ordem reversa;
3. entram em reteste os casos com IDs divergentes, confiança baixa de qualquer
   modelo ou ambiguidade indicada por qualquer modelo;
4. `a2` (Llama, ordem rotacionada) e `b2` (Qwen, ordem normal) reavaliam do zero
   exatamente o mesmo subconjunto, sem receber votos anteriores;
5. três votos coincidentes entre quatro, sem empate, formam maioria de
   estabilidade;
6. ausência de maioria 3 de 4 aciona chair automático. O SHA-256 do
   identificador interno escolhe deterministicamente Llama ou Qwen, que decide
   do zero com ordem rotacionada.

O consenso estrito exige acordo `a1/b1`, ausência de ambiguidade e confiança
diferente de baixa nos dois votos. O consenso completo usa acordo inicial,
maioria 3 de 4 ou chair para cobrir os 1.456 registros. `model_a` e `model_b`
preservam, respectivamente, os votos iniciais `a1` e `b1`.

O portfólio curado é alvo ex post e decisão operacional adotada. Por isso:

- aderência alta significa reconstruir bem a decisão da gestão;
- não significa descobrir uma verdade independente;
- divergência da referência automática é reportada como sensibilidade;
- a comparação não pode ser usada para legitimar retroativamente a curadoria.

### 4.1 Precedência temporal do alvo

Antes deste protocolo comparativo, um pipeline com `bge-m3` + K-means produziu
o candidato inicial; a gestão examinou recomendações e evidências, incorporou
critérios técnicos e estratégicos e congelou
`formacao_portfolio/decisao_curada/feedback_portfolio.json`. O arquivo
`formacao_portfolio/decisao_curada/portfolio_referencia.json` é sua projeção
analítica determinística. Depois do
congelamento, o estudo reexecutou **ambos** os métodos desde o Estágio 3.

O repositório comprova uma primeira curadoria de sete categorias no commit
`a5576c8`. O alvo final foi refinado antes do estudo para acrescentar acesso a
bases e manter Sala de Sigilo como encaminhamento fixo fora da análise. Essas
alterações são decisões gerenciais documentadas, não resultados dos placares
comparativos.

Assim, o alvo é ex post em relação ao processo de formação/curadoria e ex ante
em relação às saídas dos braços avaliados. Isso elimina a circularidade direta
de usar a saída testada como referência, mas não torna o alvo independente: o
Método Estatístico informou a formação inicial. A interpretação admissível é
aderência retrospectiva à decisão adotada, nunca verdade taxonômica universal.

## 5. Métricas e a antiga circularidade da “métrica 8”

Uma métrica que usa como verdade a própria saída do método avaliado é circular.
A v6 não faz isso. A métrica principal é
`macro_best_match_f1_services`, calculada contra projeções independentes no alvo
curado. B-cubed F1, ARI, AMI e taxa mínima de realocação são secundárias.

No Macro-F1 principal, cada um dos sete serviços substantivos recebe o mesmo
peso e é comparado ao seu melhor grupo predito; o catch-all não entra nessa
média. O pareamento é independente por serviço e não impõe correspondência
biunívoca. Por isso, uma mesma categoria predita pode ser o melhor par de mais
de um serviço; as métricas de partição, o pareamento húngaro e os diagnósticos
de fusão/fragmentação são reportados em paralelo para tornar essa eventual
mistura visível.

Mesmo assim, a independência é limitada: a referência é automática e conhece o
portfólio-alvo. Essa limitação é explícita e mitigada por:

- dois modelos de famílias distintas;
- quatro visões de referência;
- IC bootstrap;
- três seeds na ablação;
- camadas de agrupadores e chamados finais;
- tabelas de contingência e perdas por serviço;
- nenhuma referência gerada a partir da saída de um braço.

## 6. Regras de decisão

As regras numéricas completas estão em `decision_rules_v1.json`. Em síntese:

- diferença primária material: 0,03;
- conclusão forte exige ICs sem cruzar zero nas quatro referências;
- serviços estratégicos exigem suporte mínimo 5;
- perda máxima tolerada por serviço estratégico: 0,10;
- equivalência exige ICs contidos em `[-0,03, +0,03]`;
- custo só desempata equivalência e requer diferença relativa de 10%;
- seed, camada ou referência discordantes tornam o resultado sensível;
- aderência e custo nunca são fundidos em escore composto.

Conclusões admissíveis incluem superioridade, equivalência, trade-off
qualidade-custo e várias formas de inconclusividade. Um vencedor global não é
obrigatório.

## 7. Custo

O custo primário é tempo de parede dos Estágios 3–6. Tokens e GPU são reportados
separadamente. Na ablação usa-se a mediana das três réplicas. Falta de medição
impede desempate por custo; não autoriza imputação.

O job 00 também registra, para a referência automática, chamadas, tokens e
duração por modelo, além de tempo de parede e amostras de GPU do job. Esse valor
é custo comum de preparação e deve ser reportado separadamente; não entra no
ranking dos métodos, pois não varia entre os braços. O JSONL de tokens contém
respostas bem-sucedidas; tempo de parede e GPU incluem também espera e retries.

## 8. Gates de validade

Antes dos braços:

- identidade exata do Estágio 2 v6;
- máscara determinística, sem exclusões internas;
- manifesto do filtro e hashes consistentes;
- referência vinculada ao mesmo Estágio 2 e portfólio;
- contextos e código dos métodos sem Sala;
- ambiente congelado;
- entradas byte a byte idênticas.

Antes do relatório:

- todos os oito braços completos;
- seis `RUN_ID` únicos;
- telemetria válida;
- mesmas identidades de entrada;
- `VALIDACAO_RESULTS.json=PASS`.

## 9. Limitações remanescentes

- estudo retrospectivo e in-sample;
- portfólio curado é alvo gerencial, não ground truth externo;
- referência automática pode compartilhar vieses com os métodos;
- três seeds não esgotam variabilidade;
- benchmark operacional não identifica efeito causal de componentes;
- campos recomendados dependem de validação operacional posterior.

Essas limitações restringem o alcance das conclusões, mas não anulam a utilidade
da comparação para justificar qualidade, robustez e custo das abordagens.

## 10. Validade e linhagem

A execução final satisfez os gates de validade e o avaliador registrou 302
checks sem falhas. O histórico de correções operacionais não altera as regras
acima e está isolado em `../docs/APENDICE_TECNICO.md`. Somente a execução final
completa entra nas métricas e conclusões de
`../docs/RESULTADOS_COMPARACAO.md`.
