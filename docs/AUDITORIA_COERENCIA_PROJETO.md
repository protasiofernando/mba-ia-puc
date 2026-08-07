# Auditoria de coerência do projeto

Atualizada em 7 de agosto de 2026. Este documento registra a auditoria feita
antes da preparação do novo repositório. Nenhuma operação Git faz parte deste
gate.

## Veredito

**PASS.** A história metodológica, os runners, os alvos congelados e os
resultados finais descrevem o mesmo processo. O gate automatizado passou em 49
verificações, sem falhas e sem avisos:

```powershell
python scripts\validar_coerencia_projeto.py
```

O veredito não significa que o estudo prove um vencedor universal. Significa
que as alegações publicadas são rastreáveis aos artefatos e respeitam as
limitações do desenho.

## História autorizada

1. O corpus aplicado original continha 1.584 chamados.
2. Antes do Stage 1, uma regra exata sobre o `Customer Request Type` removeu
   128 chamados. Todos tinham o rótulo legado `Solicitação de Acesso a Bases de
   Dados`, pertencente ao fluxo de dados confidenciais/Sala de Sigilo e
   atendido fora da DTI Pesquisa pela equipe de Banco de Dados; os outros seis
   rótulos da lista tiveram zero ocorrências. LLM e texto
   livre não participaram dessa decisão. O universo analítico passou a ter
   1.456 chamados. O serviço curado homônimo cobre acesso comum fora da Sala.
3. Na formação histórica do portfólio, o Método Estatístico usou embeddings
   `bge-m3` e K-means no Stage 3; LLMs executaram os Stages 4–6. O commit
   histórico preservado contém o candidato automático de dez itens.
4. A área curou o candidato no nível do catálogo, primeiro para sete itens e
   depois por refinamento estratégico: acrescentou Acesso a Bases e manteve
   Sala de Sigilo como encaminhamento visível, imutável e fora da análise.
5. A decisão humana foi congelada em `feedback_portfolio.json` e projetada
   deterministicamente no alvo analítico `portfolio_referencia.json`.
6. Só depois desse congelamento os métodos Estatístico e Agêntico foram
   reexecutados na comparação. Não houve rótulo humano por chamado.
7. O Job 00 construiu uma referência automática por consenso Llama+Qwen e os
   insumos comuns. Os benchmarks compararam arquiteturas completas; os seis
   braços pareados compararam apenas o motor de descoberta em três sementes.
8. O Job 90 `2234.HPCGPU` avaliou os resultados e terminou com
   `Exit_status=0`. `VALIDACAO_RESULTS.json` passou em 302 verificações sem falhas.
9. A evidência primária e o custo favorecem o caminho estatístico, mas a
   aderência varia por camada, semente e visão de referência. Portanto não há
   vencedor global único, e o portfólio curado permanece a decisão operacional.

## O que o código realmente faz

| Fase | Runner | Contrato observado |
|---|---|---|
| Formação | `formacao_portfolio/hpc/job_formar_candidato_estatistico.sh` | executa Stages 3–6 e gera candidato; não escreve a decisão humana |
| Curadoria | edição controlada de `formacao_portfolio/decisao_curada/feedback_portfolio.json` | decisão no nível do catálogo, sem classificação manual dos 1.456 chamados |
| Projeção opcional | `scripts/hpc/job_stage7_curadoria.sh` | valida o alvo, classifica automaticamente e só então materializa volumes |
| Referência | `estudo_comparativo/hpc/job_00_referencia.sh` | valida escopo, produz consenso automático, prepara insumos e libera o setup |
| Benchmark estatístico | `job_10_m1_legado_llama.sh` | arquitetura estatística completa, Stages 3–6 |
| Benchmark agêntico | `job_20_m2_nativo.sh` | arquitetura LLM completa, Stages 3–6 |
| Comparação controlada | `job_30_ablacao.sh` | K-means × LLM, mesma interface e Estágios 4 a 6, sementes 42, 31415 e 27182 |
| Avaliação | `job_90_avaliacao.sh` | valida, audita campos, calcula métricas e gera os pacotes de resultado |

## Correções feitas nesta auditoria

- removida do README uma tabela de volumes do portfólio curado que não tinha
  um artefato Stage 7 vigente para sustentá-la;
- removida a afirmação não demonstrada de redução do *catch-all* para 1,3%;
- substituído o SHA provisório do Stage 2 pelo SHA efetivamente congelado e
  registrada sua proveniência de geração;
- corrigida a referência ao candidato automático no manifesto de origem para
  apontar ao snapshot histórico, e não aos agregados operacionais soltos;
- qualificados em `pipeline_data/README.md` os agregados de uma execução
  agêntica anterior, para que não sejam confundidos com o alvo ou com o estudo;
- retirada do fluxo formal a promoção de um Job 00 intermediário como se fosse
  a evidência final;
- formalizado este gate de coerência e integrado ao gate de publicação.
- corrigidos os metadados invertidos/antigos do `feedback_portfolio.json` e
  documentados, depois da execução, a justificativa de consolidação e o mapa
  das categorias substituídas; os bytes efetivamente executados foram
  preservados em base64 e o gate comprova que ambas as versões projetam o
  mesmo alvo analítico congelado.
- incorporada a materialização operacional posterior do Stage 7: 1.456
  classificações automáticas, sem Sala de Sigilo, com agregado publicável e
  arquivo por chamado mantido fora do Git. Essa execução não altera o alvo nem
  os resultados do Job 90.
- corrigida a descrição semântica do recorte: ela agora declara o único request
  type que efetivamente casou, a colisão de nomes com o serviço curado e o
  denominador de cada estatística; o validador privado passou a conferir também
  as categorias efetivamente removidas no relatório de filtragem.
- registrada a limitação temporal do pré-registro: a publicação consolidada
  preserva proveniência interna, mas seu histórico Git não constitui atestação
  independente de anterioridade das regras.

## Proveniência do código executado

O manifesto do pacote final contém SHA-256 para cada arquivo executado. Dos 37
arquivos críticos mapeados para a árvore mantida, 35 continuam idênticos byte a
byte. As duas diferenças são deliberadas e testadas:

- `scripts/run_stage3_kmeans_fair.py`: apenas o caminho citado na docstring foi
  atualizado de `legado_metodo1` para `metodo_estatistico`; a computação é
  idêntica;
- `scripts/projeto.py`: os caminhos foram adaptados à organização atual
  (`configuracao/`, `formacao_portfolio/decisao_curada/` e
  `dashboard/runtime/`).

Documentos do pacote foram atualizados depois da execução para incorporar o
resultado final e a reorganização. A evidência imutável continua em
`resultados_publicaveis/estudo_comparativo/MANIFESTO_PACOTE.json`; o núcleo
computacional é conferido automaticamente pelo gate.

## Limites que permanecem

- O alvo é endógeno: o candidato estatístico informou a curadoria. A métrica
  mede reconstrução retrospectiva, não acurácia contra verdade externa.
- A referência por chamado é automática e usa modelos que também participam do
  pipeline; consenso não equivale a verdade humana.
- O benchmark de arquiteturas é uma execução única e não identifica o efeito
  causal de um componente isolado.
- A generalização exige outra janela temporal ou outro portal.
- Os volumes do Stage 7 são projeções retrospectivas automáticas no catálogo
  curado; não medem adoção real depois da implantação do novo portal.

Esses limites não invalidam a contribuição. Eles determinam o alcance correto
das conclusões e impedem que a narrativa prometa mais do que o experimento
mediu.
