# Manual do Projeto

Um projeto auditável depende de que a mesma palavra signifique a mesma coisa em
todos os seus documentos. Quando o vocabulário se desloca entre arquivos, a
verificação para de ser possível: o leitor não sabe mais se dois textos
discordam ou se apenas nomeiam de forma diferente a mesma etapa.

Este manual fixa esse vocabulário único. Define a **nomenclatura padrão**, a
**estrutura de pastas**, o **pipeline e o motivo de cada etapa**, o **desenho do estudo
comparativo** e a regra **medição × conclusão**. Documentos técnicos e o histórico de
execução ficam à parte (ver §8).

---

## 1. Identidade

- **Título:** Triagem Inteligente de Chamados de TI com LLM Local.
- **Curso:** MBA BI Master (PUC-Rio).
- **Objetivo:** redesenhar o portfólio de serviços da DTI Pesquisa (FGV) a partir do
  histórico real de chamados, com todo o processamento por LLM local (nenhum dado
  sensível deixa a infraestrutura da FGV).
- **Duas contribuições:**
  1. **Aplicada:** o portfólio curado, o dashboard e o assistente de triagem.
  2. **Metodológica:** o **Estudo Comparativo de Métodos de Descoberta**.

---

## 2. Nomenclatura padrão (o que vale na monografia e no repositório)

A monografia usa **apenas** os termos formais desta tabela. Não há "versão", "revisão",
"rev", "v6" ou "hotfix" na narrativa. Esses termos descrevem detalhes de execução registrados apenas no
apêndice técnico.

| Termo formal (usar) | Definição curta |
|---|---|
| **Estudo Comparativo de Métodos de Descoberta** | A comparação controlada dos dois métodos sobre a mesma base. |
| **Método Estatístico** | Descoberta de grupos por *embeddings* `bge-m3` + K-means. |
| **Método Agêntico** | Descoberta de grupos por LLM em lotes hierárquicos. |
| **Comparação de Arquiteturas** | 1º estimando: compara os **pipelines completos** (Estágios 3–6). Resultado **descritivo** (uma execução; não isola causa). |
| **Comparação Controlada do Motor de Descoberta** | 2º estimando: mantém **tudo idêntico** e muda **só o motor de descoberta** (K-means × LLM). Isola o efeito comparativo do mecanismo neste corpus e pipeline. |
| **Portfólio curado** | O catálogo de serviços adotado pela área e utilizado como alvo do estudo. |
| **Estágios 1–6** | Extração · Interpretação · Descoberta · Rotulação · Consolidação · Classificação. |
| **Visões de referência** | Consenso estrito · consenso pleno · modelo A · modelo B. |

### 2.1 Mapa formal ↔ identificadores técnicos congelados

Os identificadores abaixo estão **congelados** dentro do experimento executado (config,
regras, resultado, pacote). Esses identificadores não são renomeados, pois sua
alteração invalidaria o resultado.
Aparecem só no código/artefatos; a monografia usa sempre o nome formal.

| Nome formal | Identificador técnico congelado |
|---|---|
| Método Estatístico | `m1_legacy_llama`, `kmeans_common_seed*` |
| Método Agêntico | `m2_native`, `llm_common_seed*` |
| Comparação de Arquiteturas | benchmark / operacional |
| Comparação Controlada do Motor de Descoberta | ablação (`*_common_*`) |
| Estudo Comparativo (pacote/execução) | `experiment_id: dti_pesquisa_comparacao_robusta_20260727_v6` |

---

## 3. Estrutura de pastas

| Pasta | Papel | Publica no git? |
|---|---|---|
| `docs/` | Documentação (este manual, técnica, resultados) | Sim |
| `scripts/` | Pipeline (Estágios 1–6), avaliador, validadores, geradores | Sim |
| `configuracao/` | Identidade do portal, contexto institucional e catálogo real | Sim |
| `formacao_portfolio/` | Snapshot, formação, contrato e decisão curada congelada | Sim |
| `estudo_comparativo/` | Código do estudo: protocolo, regras de decisão, config, jobs HPC | Sim (só código/config) |
| `resultados_publicaveis/` | Resultados agregados, métricas e gates finais validados | Sim |
| `metodo_estatistico/` | Motor estatístico mantido: formação assistida e braço do estudo | Sim |
| `dashboard/` | Painel Flask; `runtime/` recebe o banco local ignorado | Sim, exceto o banco |
| `pipeline_data/` | Artefatos agregados do pipeline (portfólio, diagnóstico) | Só agregados; por-chamado é ignorado |
| `data_exemplo/` | Saída local opcional da base sintética, gerada sob demanda | **Não**; a política pública exclui todos os CSVs |
| `data/` | CSVs reais do Jira (com PII) | **Nunca** (local) |
| `tests/` | Testes automatizados | Sim |
| `_hpc/` | Trabalho local com o HPC: `pacote/`, `insumo/`, `resultado/` | **Nunca** (local; pode ter dados por-chamado) |

Regra de privacidade: **texto ou classificação por chamado, `*.db`, CSV real,
checkpoints e o `_hpc/` nunca entram na `main` nem em refs futuras.** Só entram
agregados e código. A tag histórica `formacao-a5576c8` preserva uma única base
de 15 chamados inteiramente sintéticos, declarada e validada pelo gate;
`data_exemplo/` é, no estado vigente, uma saída local do gerador
`scripts/gerar_base_sintetica.py` e permanece ignorada.

---

## 4. O pipeline e o motivo de cada etapa

O processamento pesado roda uma vez, na infraestrutura de HPC (GPU A100), com
`llama3.3:70b` (raciocínio) e `qwen3:30b-a3b-instruct-2507-q4_K_M`
(compilação de JSON), servidos por Ollama.

| Estágio | O que faz | **Por que existe** |
|---|---|---|
| **1. Extração** | Lê os CSVs do Jira, limpa HTML, URLs e endereços de e-mail e estrutura os campos. | Transformar a exportação bruta em dados analisáveis. |
| **2. Interpretação** | A LLM destila a **intenção** de cada chamado, sem reproduzir o texto literal. | Capturar a demanda e produzir o **insumo comparável**, congelado e compartilhado por todos os métodos. |
| **3. Descoberta** | Agrupa os chamados por similaridade de intenção. | Identificar os **grupos naturais de demanda**, que constituem a **variável comparada** entre os métodos. |
| **4. Rotulação** | Nomeia e descreve cada grupo. | Tornar os grupos legíveis e acionáveis. |
| **5. Consolidação** | Organiza os tipos de requisição em grupos lógicos e estrutura o portfólio. | Transformar os grupos em um **catálogo navegável**. |
| **6. Classificação** | Associa cada chamado a uma categoria do portfólio. | Reclassificar o histórico e permitir **medir a aderência** ao alvo curado. |
| **7. Finalização curada** | A gestão congela o catálogo, e a LLM local projeta automaticamente os chamados nele. | Separar a decisão de negócio da classificação, sem exigir rótulos humanos por chamado. |

A **curadoria humana** ocorre em seguida como decisão de negócio e considera a
visibilidade dos serviços e a separação dos ambientes, critérios que os dados
não expressam. Ela é **parte do método**,
não um ajuste posterior.

Depois do encerramento do estudo comparativo, o Estágio 7 vigente foi
materializado sobre os 1.456 chamados. O agregado versionável está em
`pipeline_data/07_portfolio_final.json`; a classificação por chamado permanece
privada. Essa projeção operacional não altera o alvo congelado nem o Job 90.

### 4.1 Cronologia que formou o alvo

O alvo não foi inventado depois da comparação. A sequência auditável é:

1. o Método Estatístico (`bge-m3` + K-means) formou um candidato automático;
2. os Estágios 4 a 6 converteram os grupos em proposta operacional e evidências;
3. a área fez curadoria no nível do catálogo e gerou
   `formacao_portfolio/decisao_curada/feedback_portfolio.json`;
4. a primeira versão curada foi refinada estrategicamente, acrescentando acesso
   a bases e preservando Sala de Sigilo como encaminhamento fixo fora da análise;
5. o alvo analítico `formacao_portfolio/decisao_curada/portfolio_referencia.json`
   foi congelado como projeção
   determinística da decisão;
6. somente então os métodos Estatístico e Agêntico foram reexecutados no estudo.

O commit `a5576c8` preserva os scripts históricos; a implementação mantida e o
runner estão em `formacao_portfolio/`. Como o Método Estatístico participou da
formação, o alvo é endógeno ao processo de projeto. Por isso o estudo mede
**reconstrução retrospectiva do portfólio adotado**, não acurácia contra uma
verdade externa nem legitimação retroativa da curadoria.

Esse commit preserva também a recomendação de dez itens, a curadoria para sete
e o agregado final do Estágio 7. A versão vigente acrescentou depois Acesso a
Bases e tornou Sala de Sigilo um encaminhamento explícito. Essa evolução
gerencial é parte documentada da curadoria, não resultado da comparação.

Os 23 arquivos relevantes desse commit estão copiados byte a byte em
`formacao_portfolio/metodo_inicial_kmeans_git_a5576c8/`, com manifesto SHA-256
e verificador contra os blobs Git. Assim, a prova não depende de acesso futuro
ao GitHub nem mistura código histórico com código mantido.

---

## 5. O desenho do Estudo Comparativo

Isola a variável **modo de descoberta** e responde **duas perguntas separadas**:

1. **Comparação de Arquiteturas:** qual **pipeline completo** entrega a base mais aderente
   ao portfólio adotado? *Descritivo*: vários componentes mudam ao mesmo tempo, então não
   se atribui a diferença a um só deles, e é uma execução única.
2. **Comparação Controlada do Motor de Descoberta:** mantendo Estágio 2, Estágios 4–6,
   interface e alvo **idênticos**, muda-se **só** o motor (K-means × LLM). Isso isola o
   efeito interno do mecanismo, sem afirmar validade causal externa; o teste é repetido em
   **3 sementes**.

Garantias de rigor: mesmo `02` congelado (SHA conferido); 128 registros do request type
legado homônimo do fluxo de Sala removidos por **regra estruturada determinística**
(não por LLM) antes do Estágio 1; **4 visões** de
referência; **bootstrap** com margens **pré-registradas**; proteção dos serviços
estratégicos de baixo volume; e regra de decisão fixada **antes** dos resultados.

Universos: **1.584** chamados na base aplicada; **1.456** no universo analítico da
comparação (após a remoção estruturada de 128 chamados de escopo-Sala). Os 128 tinham
o rótulo legado `Solicitação de Acesso a Bases de Dados`, distinto do serviço curado
homônimo para acesso comum fora da Sala. Os dois denominadores são distintos **de
propósito** e devem ser identificados em toda estatística.

---

## 6. Regra: separar medição de conclusão

- **Medição** = o que sai do dado, sem opinião: Δ Macro-F1 por camada/visão, B-cubed,
  ARI, AMI, taxa de reatribuição, cobertura, custo (tempo/tokens/GPU), intervalos de
  confiança *bootstrap*. Tabelas de medição não interpretam.
- **Conclusão** = a leitura sob a **regra de decisão pré-registrada**
  (superioridade / equivalência / trade-off / inconclusivo), **sempre** declarando a
  incerteza (sensibilidade à semente/camada, execução única, referência automática).
- O **portfólio curado permanece a decisão operacional adotada**, qualquer que seja o
  vencedor metodológico.

Os documentos de resultado seguem essa separação: primeiro as tabelas (medição), depois a
seção de interpretação (conclusão), rotuladas.

---

## 7. Reprodutibilidade

- **Código do estudo:** `estudo_comparativo/` + `scripts/` + `metodo_estatistico/`.
- **Formação e curadoria:** `formacao_portfolio/` +
  `scripts/materializar_portfolio_curado.py` + `scripts/run_stage7_curadoria.py`.
- **Pacote executável (code-only):** `_hpc/pacote/` (o ZIP validado que rodou no A100).
- **Insumo congelado:** `02_summaries.json` (SHA `e4fb8e41…`), manifesto em `_hpc/insumo/`.
- **Resultado agregado (publicável):** `_hpc/resultado/` (tar público) → promovido para
  `resultados_publicaveis/` e sintetizado em
  [`docs/RESULTADOS_COMPARACAO.md`](RESULTADOS_COMPARACAO.md).
- **Runbook operacional:** `estudo_comparativo/RUNBOOK_HPC.md`.
- **Projeção operacional posterior:** `pipeline_data/07_portfolio_final.json`
  (agregado de 1.456 classificações automáticas); o arquivo por chamado é
  ignorado pelo Git.

Local vs publicável: rodar o dashboard com CSVs reais ou sintéticos é **só
local**. Qualquer pessoa pode gerar a base sintética inteiramente artificial a
partir do catálogo agregado público; ela não requer artefatos privados e não
integra o repositório público.

---

## 8. Histórico técnico

A trilha de execução registra as tentativas, as correções e a atuação dos
validadores diante de rodadas inválidas. Ela constitui evidência de
reprodutibilidade, mas permanece separada da narrativa formal. O histórico foi
consolidado em `docs/APENDICE_TECNICO.md`, enquanto o estado estruturado preserva
os detalhes legíveis por máquina.

A separação entre os dois é deliberada e vale nos dois sentidos. A narrativa
formal precisa poder ser lida sem as tentativas invalidadas, ou o resultado se
confunde com o processo. As tentativas invalidadas precisam ser preservadas, ou
a narrativa formal deixa de ser verificável. Nenhum dos dois documentos
substitui o outro.
