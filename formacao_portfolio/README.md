# Formação do portfólio adotado

Esta pasta documenta e executa a fase que **precede** o estudo comparativo. A
linhagem demonstra que o alvo da avaliação foi definido antes da observação dos
resultados comparativos dos métodos.

## Organização da pasta

```text
formacao_portfolio/
├── metodo_inicial_kmeans_git_a5576c8/  snapshot imutável do GitHub
│   ├── pipeline/                       scripts 01–07 que existiam no commit
│   ├── hpc/                            jobs históricos, inclusive Estágio 7
│   ├── pipeline_data/                  recomendação e final agregados
│   ├── feedback_portfolio.json         curadoria histórica de sete itens
│   └── MANIFESTO_SNAPSHOT.json         hashes dos 23 arquivos de origem
├── hpc/job_formar_candidato_estatistico.sh  runner mantido da formação
├── decisao_curada/                    decisão humana e espelho analítico
├── contrato_curadoria.json             transformação decisão → alvo analítico
├── MANIFESTO_ORIGEM.json               cronologia e limitações
└── verificar_snapshot.py               gate local contra hashes e blobs Git
```

O snapshot constitui evidência histórica e não recebe correções. O código atual
fica nos demais diretórios do projeto, o que distingue a execução inicial da
implementação posteriormente consolidada para o estudo. Verificação:

```powershell
python formacao_portfolio\verificar_snapshot.py
```

## Linha do tempo metodológica

1. Os chamados históricos foram interpretados nos Estágios 1–2.
2. O processo operacional inicial usou embeddings `bge-m3` e K-means para
   descobrir grupos; LLMs rotularam, consolidaram e validaram o candidato nos
   Estágios 4–6.
3. A área examinou o candidato e as evidências, aplicou critérios de gestão,
   responsabilidade, navegação e visibilidade e registrou a decisão em
   `decisao_curada/feedback_portfolio.json`.
4. A decisão foi congelada. O script
   `../scripts/materializar_portfolio_curado.py` valida sua projeção analítica em
   `decisao_curada/portfolio_referencia.json`.
5. **Só depois** o estudo comparativo reexecutou o Método Estatístico e o Método
   Agêntico sobre o mesmo insumo, medindo reconstrução do portfólio adotado,
   estabilidade e custo.

O primeiro método ajudou a **formar** a decisão e foi depois reexecutado como um
dos métodos **avaliados**. Isso torna o alvo endógeno ao processo de projeto, mas
não circular à métrica: nenhuma saída dos braços da comparação foi usada como
gabarito. O alvo é ex post em relação à formação e ex ante em relação ao estudo.

> Nota de preservação: o arquivo fornecido ao pacote final continha o rótulo
> técnico invertido `_fonte_canonica: portfolio_referencia.json` e nomenclatura
> antiga no comentário. Seus bytes estão preservados em
> `../estudo_comparativo/proveniencia_execucao/feedback_portfolio_executado.json.b64`.
> A versão canônica corrige esses metadados e documenta, depois da execução,
> justificativas e categorias substituídas. O gate comprova que ela e os bytes
> executados projetam exatamente o mesmo alvo analítico congelado.

## Evidência histórica e implementação mantida

O commit Git `a5576c8` (3 de julho de 2026) preserva o pipeline operacional que
já continha:

- `pipeline/03_cluster.py`: embeddings `bge-m3` + K-means e seleção de K por
  silhueta;
- `pipeline/04_label_clusters.py`;
- `pipeline/05_compare_portfolio.py`;
- `pipeline/06_classify_portfolio.py`;
- `pipeline/07_finalize_portfolio.py`: consumo explícito da curadoria humana.

Ele também preserva os três artefatos que provam a execução do fluxo:

- `pipeline_data/05_portfolio_recommendation.json`: 10 sugestões automáticas,
  entre elas incidentes, servidores/armazenamento, nuvem, software, HPC, VM,
  PGD, colaboração/acessos, Sala e catch-all;
- `feedback_portfolio.json`: redução humana para sete categorias operacionais;
- `pipeline_data/07_portfolio_final.json`: materialização dessas sete categorias
  com volumes, produzida pelo Estágio 7.

O runner `hpc/run_stage7.sh` daquele commit declara expressamente que roda
depois dos Estágios 1–6 e da curadoria, lê `feedback_portfolio.json` e grava os
dois artefatos `07_*`. O modelo operacional daquela execução era
`gemma4:26b-q8`; os modelos Llama/Qwen pertencem à implementação posterior e ao
estudo comparativo.

### Evolução até o portfólio vigente

O portfólio atual não é byte a byte o de 3 de julho. A curadoria posterior:

- acrescentou **Solicitação de Acesso a Bases de Dados** como serviço próprio;
- preservou **Sala de Sigilo** como item visível, fixo e encaminhado à Segurança
  da Informação, mas fora da análise;
- refinou nomes, grupos, descrições e campos obrigatórios.

Portanto, o GitHub prova o processo histórico de formação e curadoria e a origem
de sete categorias centrais. As duas decisões posteriores são evolução
estratégica explícita, não saídas ocultas de um algoritmo.

Há ainda uma limitação de linhagem no snapshot antigo: o Estágio 5 registra 1.575
chamados, enquanto o agregado do Estágio 7 registra 1.583. Esses artefatos não são
usados como base numérica da comparação final. O estudo robusto regenerou o
insumo, retirou Sala deterministicamente e congelou 1.456 chamados com SHA
próprio. A evidência histórica serve para provar a **ordem do processo**, não
para substituir os números do experimento final.

Ele preserva também os artefatos da execução:

| Artefato no commit | Evidência |
|---|---|
| `pipeline_data/05_portfolio_recommendation.json` | 1.575 chamados processados, 18 categorias vigentes, 23 grupos naturais e 10 itens no candidato |
| `feedback_portfolio.json` | primeira decisão humana registrada |
| `pipeline_data/07_portfolio_final.json` | 1.583 chamados projetados automaticamente em sete categorias curadas |

Essa primeira curadoria não é idêntica ao portfólio final congelado para o
estudo. Antes da comparação, a área fez um refinamento estratégico: acrescentou
“Solicitação de Acesso a Bases de Dados” e preservou Sala de Sigilo como
encaminhamento visível, imutável e fora da análise. Assim, a linhagem correta é
**candidato estatístico → primeira curadoria → refinamento estratégico → alvo
final congelado**. Não se afirma que o JSON final atual saiu integralmente de
uma única execução antiga.

O código mantido e endurecido desse caminho está em
`../metodo_estatistico/pipeline/`. O runner desta pasta o executa em workspace
isolado. Ele é uma reprodução operacional do processo, não uma alegação de que
cada byte ou resposta estocástica será idêntica à execução histórica.

## Artefatos e autoridade

| Artefato | Autor | Papel |
|---|---|---|
| `pipeline_data/05_portfolio_recommendation.json` | método automático | candidato; não é decisão |
| `decisao_curada/feedback_portfolio.json` | gestão/curadoria humana | decisão operacional canônica |
| `formacao_portfolio/contrato_curadoria.json` | protocolo | regras da projeção analítica |
| `decisao_curada/portfolio_referencia.json` | transformação determinística | espelho congelado para avaliação |
| `pipeline_data/07_classificados_final.json` | LLM local | projeção automática por chamado; privada |
| `pipeline_data/07_portfolio_final.json` | materializador | visão agregada do portfólio adotado |

### Separação entre arquivo vigente e evidência executada

A versão vigente de `decisao_curada/feedback_portfolio.json` usa linguagem
limpa, registra corretamente seu papel e explicita a justificativa e o mapa de
consolidação. A cópia exata fornecida à execução, inclusive seus dois
metadados antigos e sem esse enriquecimento editorial posterior, está na área
de proveniência. A autoridade metodológica correta, adotada pelos documentos e
imposta pelo materializador, é:

```text
decisao_curada/feedback_portfolio.json (decisão humana)
  -> contrato_curadoria.json (regras analíticas)
  -> decisao_curada/portfolio_referencia.json (espelho para o estudo)
```

O gate reconstrói o mesmo espelho a partir das duas versões e também confere o
SHA da evidência executada, sem confundir proveniência técnica com documentação
vigente.

Para auditar automaticamente a origem no histórico Git:

```bash
python scripts/verificar_origem_formacao.py
```

O comando verifica os blobs, os metadados do candidato, os marcadores
`bge-m3`/K-means/silhueta e a materialização da primeira curadoria.

Sala de Sigilo permanece no portfólio visível, mas é fixa, atendida pela
Segurança da Informação e não participa de descoberta, classificação analítica,
métricas ou ranking.

## Como reproduzir a formação

O Estágio 2 vigente deve existir em `pipeline_data/02_summaries.json` e passar no
gate de 1.456 registros e SHA congelado. No HPC:

```bash
cd ~/mba-ia-puc
qsub formacao_portfolio/hpc/job_formar_candidato_estatistico.sh
```

O job gera o candidato em
`formacao_portfolio/execucao/pipeline_data/05_portfolio_recommendation.json` e
uma classificação automática de cobertura no `06_classificados.json`. Ele
**nunca** escreve a decisão humana.

Após a revisão gerencial, a pessoa responsável edita
`decisao_curada/feedback_portfolio.json`. Não há classificação manual dos 1.456 chamados. O
gate determinístico é:

```bash
python scripts/materializar_portfolio_curado.py
```

Para materializar automaticamente a classificação operacional e os volumes do
portfólio adotado no HPC:

```bash
qsub scripts/hpc/job_stage7_curadoria.sh
```

O arquivo por chamado é privado e ignorado pelo Git; o agregado do portfólio
pode ser publicado depois de inspeção de privacidade.

## Como começa a comparação

Com os dois JSONs de `decisao_curada/` congelados, segue-se
o runbook em `../estudo_comparativo/RUNBOOK_HPC.md`: Job 00, dois benchmarks,
seis braços pareados e Job 90. A comparação não escolhe retroativamente o
portfólio e não precisa decretar um vencedor. Ela descreve aderência relativa,
robustez, custo e prós/contras dos dois caminhos.
