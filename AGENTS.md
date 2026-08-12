# Guia rapido para agentes

Este repositorio e o projeto de MBA `mba-ia-masterbi-puc`, sobre reorganizacao
auditavel do catalogo de servicos da DTI Pesquisa FGV a partir de chamados do
Jira Service Management.

Nos artefatos novos use o identificador `mba-ia-puc`. A execução final do
protocolo foi a revisão técnica `rev6`; na narrativa formal prefira os nomes
dos métodos e estimandos, sem nomes de revisão ou `hotfixN`.

Antes de agir, leia nesta ordem:

1. `docs/RESUMO_EXECUTIVO.md` - contexto minimo, resultado e proxima acao;
2. `docs/ESTADO_COMPARACAO_ROBUSTA.json` - estado canonico estruturado;
3. `docs/STATUS_PROJETO.md` - status humano curto;
4. documentos longos somente se a tarefa exigir auditoria profunda.

## Estado vigente em uma frase

A comparação está concluída. Sala de Sigilo foi removida deterministicamente
antes do Estágio 1; o universo analítico tem 1.456 chamados; o Job 90 final
`2234.HPCGPU` terminou com `Exit_status=0`; `VALIDACAO_RESULTS.json` passou em
302 checks, sem falhas. A evidência primária favorece K-means e seu custo, mas
não há vencedor global único de aderência por sensibilidade a semente, camada
e referência. O portfólio curado permanece a decisão operacional. Não há job
pendente nem motivo para reexecutar a cadeia. A precedência do alvo está
formalizada em `formacao_portfolio/`: candidato inicial pelo Método Estatístico,
curadoria humana no nível do catálogo, congelamento e só depois comparação dos
dois métodos. O Estágio 7 automático foi materializado depois da comparação sobre
os 1.456 chamados e não exige rótulos humanos por chamado; seu agregado pode ser
publicado, mas a classificação por chamado continua privada.

## Regras que nao podem ser quebradas

- Nao reutilize artefatos v5 nem o Estágio 2 antigo de 1.584 registros.
- Nao trate Sala de Sigilo como parte da analise; ela fica visivel no portfolio,
  mas fora dos metodos, metricas e ranking.
- Nao envie CSVs, `01_tickets`, `02_summaries`, checkpoints, bancos ou `.env`
  para Git, ZIP code-only ou servicos externos.
- Para a comparacao robusta, o ZIP e code-only; o Estágio 2 e copiado dentro do
  HPC.
- O portfolio curado e a decisao operacional adotada, nao uma ground truth
  independente.
- A comparacao mede aderencia, robustez e custo; conclusao numerica so existe
  depois do `job_90` e de `VALIDACAO_RESULTS.json=PASS`.
- Quando um comando do usuario for gate de execucao, limpeza ou retomada,
  aguarde a saida antes de encadear.

## Mapa minimo

```text
scripts/                 runners, validadores e geradores de pacote
dashboard/               Flask local
configuracao/            identidade, contexto e catalogo institucional
data/                    CSVs sensiveis, fora do git
pipeline_data/           agregados versionaveis e saidas locais permitidas
formacao_portfolio/      linhagem, formacao e decisao curada congelada
estudo_comparativo/      protocolo, jobs PBS, regras e runbook do estudo
docs/                    narrativa, resultado, estado e apendice tecnico
metodo_estatistico/      motor usado na formacao e reexecutado na comparacao
resultados_publicaveis/  metricas agregadas e gates finais seguros para Git
```

Para explicar tecnicamente o projeto do zero, use
`docs/FLUXO_COMPLETO_MBA.md` como fonte canônica.

## Modelos e infraestrutura

- HPC/Azure com GPU NVIDIA A100;
- Ollama local em `127.0.0.1:11434`;
- `llama3.3:70b` para raciocinio;
- `qwen3:30b-a3b-instruct-2507-q4_K_M` para JSON estrito;
- `bge-m3` para embeddings onde declarado.

## Validacoes locais uteis

```powershell
python -m pytest -q
python scripts/validar_coerencia_projeto.py
python scripts/verificar_publicacao_novo_repo.py --full
python -B -c "import ast, pathlib; files=list(pathlib.Path('scripts').glob('*.py'))+[pathlib.Path('dashboard/app.py')]; [ast.parse(p.read_text(encoding='utf-8-sig'), filename=str(p)) for p in files]; print('Python syntax ok')"
python -c "import json; json.load(open('docs/ESTADO_COMPARACAO_ROBUSTA.json', encoding='utf-8-sig')); print('json ok')"
python scripts/verificar_publicacao_novo_repo.py --full
```
