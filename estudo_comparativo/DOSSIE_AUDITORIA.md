# Dossiê de auditoria — comparação robusta

## Sumário executivo

A primeira tentativa não produziu comparação: o próprio gate abortou o Job
2165 porque a LLM excluiu 702 de 1.584 chamados como Sala de Sigilo. A máscara
foi invalidada. O desenho final corrigiu a fronteira na fonte: removeu 128
chamados pelo request type estruturado antes do Stage 1 e entregou os 1.456
remanescentes igualmente a todos os braços. Nenhum modelo decide Sala.

Estado atual:

| Componente | Estado |
|---|---|
| CSVs filtrados | PASS: 1.456 linhas e chaves únicas |
| Manifesto agregado do filtro | Congelado |
| Código Stage 1–2 isolado | Implementado |
| ZIP Stage 1–2 code-only | Gerado e auditado |
| Stage 2 | Concluído no Job `2166.HPCGPU`, `Exit_status=0` |
| SHA Stage 2 | `e4fb8e41c910f8f2ed6151d8e69515ae8fd1b01f1310d47fa680d4403fd54ff1` |
| ZIP executado | `mba-ia-puc_rev6_20260803.zip`, SHA `a2896c3e…b1967c` |
| Jobs de comparação | Concluídos |
| Validação final | PASS: 302 checks, zero falhas |
| Resultado | Dependente da camada; sem vencedor global único |

## 1. Objetivo de negócio

O produto final é um portfólio de serviços que cubra as demandas reais e defina
quais informações o usuário deve informar ao abrir um chamado. O método
automático gera evidências e recomendações; a curadoria humana final incorpora
decisões técnicas, responsabilidade, governança e visibilidade.

A comparação metodológica responde qual abordagem reconstrói melhor essa decisão
curada, com que robustez e custo. Ela não elimina a curadoria.

## 2. Por que a comparação é justa

O benchmark operacional e a ablação justa são apresentados separadamente.

No benchmark, M1 e M2 são arquiteturas inteiras; qualquer superioridade é
descritiva. Na ablação, K-means e LLM recebem:

- o mesmo Stage 2;
- os mesmos 1.456 registros e ordem;
- a mesma interface intermediária;
- os mesmos Stages 4–6;
- o mesmo portfólio-alvo;
- o mesmo avaliador;
- três seeds pareadas;
- o mesmo ambiente HPC.

Isso isola melhor o motor de descoberta e evita atribuir ao clustering diferenças
causadas por prompts, classificadores ou pós-processamento distintos.

## 3. Circularidade e alvo curado

A antiga “métrica 8” seria circular se comparasse cada método com rótulos
derivados dele próprio. A v6 não usa saídas de nenhum braço como referência.

Ainda existe uma circularidade conceitual limitada: mede-se aderência a uma
decisão curada e a referência automática conhece esse alvo. Portanto, a
conclusão válida é “método mais aderente ao portfólio adotado neste corpus”, não
“método objetivamente verdadeiro”.

A blindagem inclui:

- quatro visões de referência;
- dois modelos distintos;
- IC bootstrap;
- três seeds;
- métricas por duas camadas;
- perdas por serviço estratégico;
- métricas estruturais sem mapeamento único;
- custo separado;
- possibilidade explícita de resultado inconclusivo.

## 4. Sala de Sigilo

Sala é um item fixo do portal, atendido pela Segurança da Informação. Não deve
ser lida, modificada ou analisada pelos métodos.

Na v6, a exclusão ocorre nos CSVs originais pelo campo
`Customer Request Type`. O manifesto agregado registra:

| Arquivo | Antes | Removidos | Depois | SHA pós-filtro |
|---|---:|---:|---:|---|
| 2024 | 733 | 21 | 712 | `b7f31a…d69ab` |
| 2025 | 638 | 74 | 564 | `d7bafe…ea7d5` |
| 2026 | 213 | 33 | 180 | `a979d7…2d03f` |

Não se usa texto livre. Assim, menções incidentais a Sala em comentários não
alteram o escopo.

O job 00 cria uma máscara que inclui todo o Stage 2 v6 e falha se houver
exclusão, indeterminação, hash ou ordem divergente.

## 5. Linhagem de dados

```text
CSVs originais (1.584)
  -> filtro estruturado exato (remove 128)
CSVs v6 (1.456; hashes congelados)
  -> Stage 1 novo, diretório isolado
01_tickets v6
  -> Stage 2 novo, checkpoints isolados
02_summaries v6 (SHA e4fb8e41c910f8f2ed6151d8e69515ae8fd1b01f1310d47fa680d4403fd54ff1)
  -> cópia server-side para pacote final
máscara determinística (inclui 1.456)
  -> referência Llama+Qwen
  -> oito braços
  -> job 90
```

O relatório privado de filtragem e os outputs por chamado não entram no Git nem
nos ZIPs code-only.

## 6. Implementação dos gates

### Antes do Stage 1

`validar_filtro_sala_sigilo_v6.py` verifica:

- nomes exatos dos três CSVs;
- SHA-256 de cada arquivo;
- cardinalidade por período;
- zero request types proibidos;
- 1.456 chaves preenchidas e únicas.

### Depois do Stage 2

`registrar_stage2_comparacao_v6.py` verifica:

- 1.456 registros nos Stages 1 e 2;
- mesmas chaves e mesma ordem;
- chaves únicas;
- schema mínimo;
- hashes de Stage 1, Stage 2 e manifesto;
- nome e digest completo do modelo Ollama;
- versão do contrato, temperatura e hashes do código Stage 2/cliente LLM.

Ele grava apenas metadados agregados em `MANIFESTO_STAGE2_V6.json`.

### Geração do pacote final

`gerar_pacote_comparacao_robusta.py` exige esse manifesto. O script falha se:

- geração não for v6;
- escopo tiver usado LLM;
- quantidade não for 1.456;
- SHA do Stage 2 for inválido;
- manifesto de escopo divergir.

O SHA do Stage 2 é injetado no `experimento_config.json` dentro do ZIP. Logo, o
pacote final não pode ser produzido antecipadamente com placeholder.

### Job 00

1. valida identidade do Stage 2;
2. materializa máscara determinística;
3. congela ambiente;
4. cria referência automática;
5. distribui a entrada byte a byte;
6. executa `VALIDACAO_SETUP`.

#### Auditoria das passagens da referência

- `a1`/Llama e `b1`/Qwen avaliam todos os 1.456 registros;
- `b1` recebe categorias em ordem reversa para controlar efeito de posição;
- `a2` e `b2` recebem o mesmo subconjunto: desacordo inicial, confiança baixa
  de qualquer modelo ou ambiguidade de qualquer modelo;
- ambos os retestes decidem do zero, sem acesso aos votos anteriores;
- cobertura por reteste exige maioria não empatada de pelo menos 3 em 4;
- casos restantes recebem chair Llama ou Qwen, distribuído
  deterministicamente pelo SHA-256 do identificador opaco;
- consenso estrito não usa chair e exige acordo inicial sem baixa confiança ou
  ambiguidade;
- consenso completo cobre todos os registros, mas continua sendo referência
  automática, não ground truth humana.

Os checkpoints são separados por fase, passagem, modelo e fingerprint do
prompt. Isso permite retomar uma interrupção sem misturar respostas produzidas
por outro prompt, modelo ou insumo.

## 7. Métricas e decisão

Métrica primária: `macro_best_match_f1_services`.

Secundárias:

- B-cubed F1;
- ARI;
- AMI;
- taxa mínima de realocação.

Gates:

- margem primária 0,03;
- ICs nas quatro referências;
- suporte estratégico mínimo 5;
- perda estratégica máxima 0,10;
- equivalência apenas com IC integral dentro da margem;
- custo como desempate só em equivalência.

O relatório deve poder dizer “inconclusivo”. Forçar um vencedor violaria o
pré-registro.

## 8. Informações de abertura de chamados

Os campos do formulário são uma saída do portfólio curado e devem ser avaliados
por:

- necessidade operacional;
- capacidade de o usuário responder;
- impacto no roteamento e tempo de atendimento;
- minimização de dados;
- diferenças entre serviços.

Sala de Sigilo não recebe campos neste projeto. Seu formulário pertence à equipe
responsável.

## 9. Evidência da v5

O histórico completo está em `docs/APENDICE_TECNICO.md` no repositório e em
`APENDICE_TECNICO.md` nos pacotes reconstruídos após a reorganização. Elementos
essenciais:

- pacote v5 SHA `5bc5b48b…b897329`;
- job `2165.HPCGPU`, exit 1;
- 879 incluídos, 702 Sala, 3 indeterminados;
- máscara e `02_summaries_escopo` inválidos;
- nenhum vencedor.

Preservar essa evidência demonstra que a auditoria detectou e corrigiu uma falha,
em vez de ocultar uma rodada desfavorável.

## 10. Resultado da auditoria

O estudo foi concluído pelo Job 90 `2234.HPCGPU`, com `Exit_status=0`.
`VALIDACAO_RESULTS.json` registrou `PASS`, 302 checks e zero falhas. A
conclusão formal é dependente da camada tanto no benchmark quanto na ablação.
A evidência primária favorece K-means, mas não sustenta vencedor global único;
o custo favorece o motor estatístico.

A referência automática continua sendo uma limitação declarada: ela mede
aderência ao portfólio curado e não substitui um gold standard humano externo.
Por isso, o portfólio curado permanece a decisão operacional, e as métricas são
evidência de apoio.

Os detalhes dos incidentes de escopo, IDs fechados, contratos, freeze de código
e segunda opção opcional foram deslocados para
`../docs/APENDICE_TECNICO.md`. Os números finais e sua interpretação estão em
`../docs/RESULTADOS_COMPARACAO.md`.
