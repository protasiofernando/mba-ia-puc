# Manual HPC vigente

## Escolha primeiro o fluxo

### Pipeline operacional

Use quando a intenção é processar CSVs do Jira e atualizar a recomendação:

```bash
cd <raiz-do-projeto>
qsub scripts/hpc/job_pipeline.sh
```

Entradas: `data/` e os arquivos de `configuracao/` (`projeto.json`,
`config_portfolio.json` e `contexto_catalogo.md`).

### Comparação metodológica

Use quando a intenção é comparar métodos sobre o Estágio 2 congelado:

[`../estudo_comparativo/RUNBOOK_HPC.md`](../estudo_comparativo/RUNBOOK_HPC.md)

Esse fluxo recebe um ZIP code-only, não CSVs. Não execute Estágio 1 ou 2 dentro da
comparação.

## Ambiente vigente

- GPU: A100;
- Ollama em `127.0.0.1:11434`;
- raciocínio: `llama3.3:70b`;
- JSON estruturado: `qwen3:30b-a3b-instruct-2507-q4_K_M`;
- embeddings: `bge-m3`;
- venv padrão dos jobs de comparação: `~/venvs/venv`;
- model store padrão: `~/ollama/models`.

Cada job da comparação:

- verifica a A100;
- garante os três modelos;
- registra digests, GPU, CPU, Python, `pip freeze` e BLAS;
- compara o ambiente com o snapshot do job 00;
- mede tempo, chamadas e GPU por stage;
- encerra o Ollama ao terminar.

## Regras operacionais

- use diretório novo por execução experimental;
- valide `bash -n` antes do primeiro `qsub`;
- rode um job da comparação por vez;
- acompanhe `qstat` e `tail -F`;
- não edite arquivos durante uma rodada;
- não apague checkpoints em falha transitória;
- não use outputs de outra versão;
- não copie dados sensíveis para o Git.

## Diagnóstico mínimo

```bash
nvidia-smi
ollama --version
python --version
python -m pip freeze
```

Para a comparação, os jobs fazem essas capturas automaticamente. Uma diferença
de ambiente gera falha, não aviso silencioso.

## Retorno

Pipeline operacional: transfira somente agregados permitidos e mantenha
artefatos por chamado na infraestrutura institucional.

Comparação robusta:

- tar público: pode ser revisado para banca/Git;
- tar privado: armazenamento restrito;
- preserve também o ZIP original, porque ele contém o código/configuração
  exatos da rodada.
