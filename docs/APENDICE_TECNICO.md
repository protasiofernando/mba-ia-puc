# Apêndice técnico: linhagem, falhas e correções do experimento

Cada falha registrada aqui foi interrompida por um controle diferente, antes de
contaminar a comparação. É por isso que elas pertencem à documentação do
resultado e não a uma ressalva sobre ele: a sequência de tentativas invalidadas
é a evidência de que os gates funcionam.

Este documento preserva a linhagem de execução fora da narrativa principal do
MBA. Ele registra por que tentativas anteriores não são resultados, como cada
gate atuou e qual execução produziu os artefatos finais. A fonte estruturada
mais detalhada é `ESTADO_COMPARACAO_ROBUSTA.json`; o resultado científico está
em `RESULTADOS_COMPARACAO.md`.

## 0. Formação do portfólio antes do experimento

O snapshot público preservado do commit histórico `a5576c8` mostra que o alvo
não foi criado a partir dos placares da comparação. Antes do estudo robusto, já
existiam:

- `pipeline/03_cluster.py`, com embeddings `bge-m3`, K-means e seleção de K por
  silhueta;
- os Estágios 4–6 de rotulação, recomendação e classificação;
- `pipeline/07_finalize_portfolio.py`, que lê explicitamente
  `feedback_portfolio.json` como curadoria humana;
- o candidato `05_portfolio_recommendation.json`, com 1.575 chamados, 23 grupos
  naturais e 10 itens sugeridos;
- o `07_portfolio_final.json`, com 1.583 projeções automáticas em sete categorias
  da primeira curadoria.

O portfólio final congelado para a comparação é uma evolução dessa primeira
decisão. A gestão acrescentou “Solicitação de Acesso a Bases de Dados” e
preservou Sala de Sigilo como encaminhamento visível, imutável e fora da
análise. Portanto, a linhagem é candidato estatístico, curadoria inicial,
refinamento estratégico e congelamento. Só depois os dois métodos foram
reexecutados.

Os blobs Git auditados e os runners mantidos estão registrados em
`../formacao_portfolio/MANIFESTO_ORIGEM.json`. Essa precedência elimina a
circularidade direta de usar a saída de um braço como alvo, mas não transforma
o portfólio em referência externa independente: o caminho estatístico informou sua
formação.

Essa evidência histórica demonstra a precedência do alvo, não funciona como
atestação externa da anterioridade das regras de decisão. O repositório público
foi consolidado depois da execução e contém protocolo, regras e resultados no
mesmo commit-raiz. Portanto, hashes, manifestos, timestamps de jobs e este
apêndice devem ser lidos como proveniência interna auditável, não como um
pré-registro com carimbo de tempo independente. Uma replicação futura deve
depositar as regras em um serviço externo imutável antes de liberar resultados.

O arquivo fornecido à execução continha um campo legado `_fonte_canonica` no
sentido inverso e nomenclatura técnica antiga no comentário. Seus bytes foram
preservados em
`../estudo_comparativo/proveniencia_execucao/feedback_portfolio_executado.json.b64`.
A versão humana canônica corrige esses metadados e acrescenta, para auditoria
gerencial, `justificativa_consolidacao` e `substitui_categorias_atuais`. Esses
campos foram documentados depois da execução: não mudam IDs, campos de
classificação nem a projeção analítica. Tanto o artefato executado quanto o
vigente projetam o mesmo `portfolio_referencia.json`, como validado por
`scripts/materializar_portfolio_curado.py`.

## 1. Fronteira de escopo invalidada

A primeira tentativa usou 1.584 chamados e delegou a Llama e Qwen a decisão de
excluir Sala de Sigilo. O Job `2165.HPCGPU` abortou com `Exit_status=1` porque
702 registros (44,318%) foram marcados como Sala, acima do teto
pré-registrado de 25%. Llama marcou 43,69%, Qwen 18,88% e houve 381 casos em
que Llama votou Sala duas vezes enquanto Qwen votou incluir duas vezes. Algumas
justificativas negavam relação com Sala, embora o ID retornado determinasse a
exclusão.

Essa máscara é inválida e nenhum artefato dela pode alimentar a comparação. O
ZIP dessa tentativa tinha SHA-256
`5bc5b48b0b30be82275b3f73142bc1034cc87d3b01e9f96eb8f4fecf5b897329`;
ele é somente evidência histórica.

A correção foi retirar a decisão de escopo das LLMs. O campo estruturado
`Customer Request Type` identificou 128 registros; todos tinham o valor legado
`Solicitação de Acesso a Bases de Dados`, classificado institucionalmente no
fluxo de dados confidenciais/Sala de Sigilo e atendido fora da DTI Pesquisa
pela equipe de Banco de Dados. Os outros seis request types da lista de
exclusão tiveram zero ocorrências no período:

| Período | Antes | Removidos | Depois |
|---|---:|---:|---:|
| 2024 | 733 | 21 | 712 |
| 2025 | 638 | 74 | 564 |
| 2026 | 213 | 33 | 180 |
| **Total** | **1.584** | **128** | **1.456** |

O filtro passou a ser determinístico, anterior ao Estágio 1, sem texto livre e
sem LLM. Sala permaneceu visível no portfólio como encaminhamento da Segurança
da Informação, mas saiu do universo, das métricas e do ranking.

Há uma colisão de nomes que precisa ser preservada na leitura. O serviço final
curado `Solicitação de Acesso a Bases de Dados` não reintroduz os 128 registros:
ele substitui `Acessar pastas de dados de pesquisa` e atende acesso comum a
pastas e bases fora da Sala de Sigilo. A decisão curada já registra essa
distinção em `feedback_portfolio.json`.

Por integridade de proveniência, os bytes executados não foram reescritos depois
do resultado. Assim, `decision_rules_v1.json` usa “Sala de Sigilo” como síntese
operacional em `primary_universe`, e alguns campos congelados mantêm o prefixo
técnico legado `n_sala_*`. Esses nomes significam “remoção upstream do escopo
de Sala” e não afirmam que o texto literal “Sala” aparecia no request type. O
manifesto e a narrativa mantida acima fornecem a interpretação semântica exata.

A mesma decisão explica um resíduo mais visível. O parágrafo de abertura de
`resultados_publicaveis/estudo_comparativo/avaliacao/RESULTADO_COMPARACAO_ROBUSTA.md`
descreve a máscara de escopo como automática e conservadora, decidida por voto,
ambiguidade ou confiança. É a descrição do procedimento invalidado no Job
`2165.HPCGPU`, e não do filtro determinístico que efetivamente rodou. O texto é
um literal fixo do gerador, herdado da geração anterior, que não acompanhou a
mudança de método da v6.

Corrigir esse literal exigiria editar `scripts/avaliar_comparacao_robusta.py`,
cujo SHA-256 está registrado em `MANIFESTO_PACOTE.json` e cuja cópia neste
repositório permanece byte-idêntica à que foi executada. A escolha foi preservar
essa igualdade. Um rótulo herdado, documentado e contradito pelo próprio
relatório custa menos à auditoria do que a perda da prova de que o código
publicado é o código executado. Como o projeto não tem execução pendente, a
correção do gerador só teria efeito numa reexecução que a política registrada em
`STATUS_PROJETO.md` não autoriza.

O leitor que encontrar o parágrafo antigo deve consultar a nota editorial em
`../resultados_publicaveis/README.md`, que reúne a formulação legada, o
procedimento canônico e a linha do próprio relatório que o confirma.

## 2. Insumo analítico congelado

O Job `2166.HPCGPU` regenerou os Estágios 1 e 2 no universo corrigido e terminou
com `Exit_status=0`. O Estágio 2 válido tem 1.456 registros e SHA-256
`e4fb8e41c910f8f2ed6151d8e69515ae8fd1b01f1310d47fa680d4403fd54ff1`.
O SHA antigo de 1.584 registros é proibido. Todos os braços finais receberam
cópias byte-idênticas do novo insumo.

O código que reproduz essa preparação foi retirado da raiz e está agora em:

- `scripts/hpc/job_pipeline.sh`: runner geral dos Estágios 1–6;
- `estudo_comparativo/hpc/job_preparar_insumo.sh`: wrapper isolado dos Estágios
  1–2 e do manifesto agregado.

Os nomes foram simplificados após a execução. Os caminhos remotos originais,
nomes de pacote e hashes permanecem no estado JSON como proveniência do que de
fato rodou.

## 3. Referência automática e integridade do código

Os Jobs `2167` e `2168` expuseram um erro de parsing de IDs com prefixo. Uma
correção direta no workspace conseguiu avançar, mas foi rejeitada pelo gate de
integridade porque o código já não correspondia ao manifesto congelado. Isso
demonstrou que o freeze impedia remendos silenciosos.

O Job `2169.HPCGPU`, em workspace limpo, passou. Em uma revisão posterior, o
Job `2182.HPCGPU` também concluiu integralmente o Job 00. A referência final foi
sempre reconstruída em workspace novo quando código relevante mudou.

A referência não é humana: Llama e Qwen projetam todos os 1.456 chamados no
portfólio curado fechado; casos de desacordo, baixa confiança ou ambiguidade
recebem as passagens `a2/b2`, e os casos ainda sem maioria recebem um chair
automático. Essa referência mede aderência ao portfólio adotado, não verdade
externa.

## 4. Falhas do Estágio 5 e proteção de destinos fechados

O Job `2172.HPCGPU` falhou porque o mínimo de categorias era validado antes do
merge determinístico de uma categoria obrigatória. A ordem do contrato foi
corrigida; os sucessores foram corretamente bloqueados por `afterok`.

Na cadeia seguinte, os Jobs `2183` a `2189` concluíram, mas o último braço,
`2190.HPCGPU`, falhou no Estágio 5a.3: a LLM retornou
`test_e_projeto_4c2cd10d` em vez do destino canônico
`teste_e_projeto_4c2cd10d`. A retomada única `2192.HPCGPU` reproduziu o erro e
acionou o gate de parada. A correção posterior passou a aceitar uma variação
somente quando o digest hexadecimal identificava de forma única o destino
canônico; não foi introduzido fuzzy matching.

## 5. Desalinhamento entre produtor e validador

O Job `2196.HPCGPU` gerou um Estágio 5 com o contrato
`closed-destination-stage4-evidence-v3`, mas o validador empacotado ainda
exigia `v2`. Foi uma falha de integração, não do método ou do modelo. A correção
alinhou produtor, artefato e validador e adicionou testes e preflight do ZIP.

Na cadeia seguinte, os oito braços terminaram, mas o Job 90 `2213.HPCGPU`
falhou porque o avaliador comparava nomes como `ollama:llama3.3:70b` com
`llama3.3:70b` por igualdade literal. Os digests dos modelos estavam corretos.
Uma tentativa de editar o avaliador in-place (`2214`) foi barrada pelo freeze,
como previsto. O prefixo passou a ser normalizado sem relaxar a validação por
digest.

## 6. Segunda opção opcional no Estágio 6

Na cadeia posterior, o Job 00 e o benchmark legado passaram, mas o Job
`2217.HPCGPU` terminou com erro após quatro respostas conterem uma segunda
opção inexistente. A categoria primária era válida e a segunda opção era
opcional, porém o código descartava o chamado inteiro.

A correção final preserva a categoria primária, descarta apenas a segunda opção
inválida, registra `segunda_opcao_descartada=true` e recomenda revisão. Campos
obrigatórios continuam fail-closed. Como essa mudança afeta código de método,
ela exigiu novo pacote, workspace, Job 00 e execução integral.

## 7. Execução final válida

A execução final ocorreu no workspace HPC `~/mba-ia-puc_rev6`, com o pacote
code-only `mba-ia-puc_rev6_20260803.zip`:

- SHA-256 do ZIP:
  `a2896c3e46f0b8d6dc90660a8715bf719effcfd55af4964e3486cb9283b1967c`;
- tamanho: 210.750 bytes;
- Estágio 2: 1.456 registros, SHA-256 `e4fb8e41…54ff1`;
- Job 90 final: `2234.HPCGPU`, `Exit_status=0`, walltime `00:01:04`;
- `VALIDACAO_RESULTS.json`: `PASS`, 302 verificações, zero falhas;
- conclusão registrada em 4 de agosto de 2026 às 13:11:23 -03.

Artefatos locais:

| Artefato | SHA-256 |
|---|---|
| Tar público | `f476e4103044ee0cc578597523689cbafaf7b2b164fa720a5078808bc4545be6` |
| Tar privado | `a8c66f9a1923c98a5756566040b1b8f216c586d46ed9f3d3a933641e741053eb` |
| Validação final | `fd0c98e51b6330a7b5d42a0c92b517c2dc729b1d83acff2ae15bbe6f5f3b565a` |
| Métricas consolidadas | `2ec80b28fe8db496154adb722b3ff8cf8b6de70c4f5dadbbfe9667858930a798` |

O tar privado contém dados por chamado e não deve ser versionado ou enviado a
serviços externos. O tar público foi inspecionado quanto a chaves e texto de
chamados.

O ZIP executado deve ser preservado como prova byte a byte. Um rebuild feito
após esta reorganização documental não tem o mesmo SHA global, porque caminhos
e textos auxiliares foram renomeados (`estudo_comparativo/`,
`metodo_estatistico/` e este apêndice). A auditoria comparativa encontrou
igualdade no código algorítmico, prompts, parâmetros e regras; as diferenças
foram de documentação/nomenclatura e do manifesto derivado. Assim, a
reprodutibilidade metodológica permanece, mas a reprodução binária exata exige
o ZIP original em `_hpc/pacote/`.

Essa igualdade é verificável arquivo a arquivo, e não apenas afirmada. Das
entradas de `resultados_publicaveis/estudo_comparativo/MANIFESTO_PACOTE.json`,
**29 continuam byte-idênticas às cópias versionadas neste repositório**:

| Grupo | Arquivos |
|---|---:|
| Scripts do método, avaliador e validadores empacotados | 18 |
| Jobs PBS do estudo | 6 |
| Regras e configuração do experimento | 3 |
| `configuracao/projeto.json` | 1 |
| `estudo_comparativo/requirements_comparacao.txt` | 1 |

Estão nesse conjunto `decision_rules_v1.json`, `experimento_config.json`,
`filtro_sala_sigilo_manifest_v6.json`, os cinco jobs mais `job_lib.sh` e todo o
caminho de código que produziu as métricas, incluindo
`avaliar_comparacao_robusta.py`. Qualquer pessoa confirma calculando o SHA-256
de cada arquivo e comparando com o manifesto. Os itens que divergem são
documentos editados depois da execução, e nenhum deles participa do cálculo.

Portanto, a afirmação defensável é mais forte do que “reprodutibilidade
metodológica”: as regras de decisão, os parâmetros e o código que gerou os
números publicados são, byte a byte, os que rodaram no Job 90.

## 8. Leitura metodológica das falhas

As falhas anteriores não devem ser contadas como réplicas, resultados negativos
ou evidência a favor de um método. Elas foram falhas de escopo, parsing,
contrato ou integração e foram barradas antes da conclusão. O uso de
`afterok`, workspaces novos, manifesto, freeze de ambiente e validações finais
impediu que resultados parciais contaminassem a comparação.

O resultado científico válido é exclusivamente o descrito em
`RESULTADOS_COMPARACAO.md`: a evidência primária favorece K-means, mas não há
vencedor global único de aderência devido à sensibilidade à semente e à camada;
o custo favorece a alternativa estatística; o portfólio curado permanece a
decisão operacional.

Há um limite nessa leitura, e convém deixá-lo explícito. Um gate só barra a
falha que foi previsto para barrar, e todas as classes registradas acima foram
detectadas por controles escritos antes delas. Nada aqui demonstra que a
execução aprovada esteja livre de uma falha silenciosa, de tipo não antecipado.
O que o registro sustenta é mais modesto e ainda assim útil: sempre que o
aparato detectou um problema, ele interrompeu a cadeia em vez de produzir um
número.
