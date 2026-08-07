# Publicação final com histórico Git zerado

Este documento define a publicação definitiva no repositório novo e vazio
`protasiofernando/mba-ia-puc`. A `main` remota deve conter a árvore code-only
validada em **um único commit-raiz**, sem herdar os commits dos repositórios
reaproveitados. Ao final, não deve existir outra branch nem tag.

A auditabilidade metodológica não depende do histórico público anterior. O
snapshot imutável em `formacao_portfolio/`, seus hashes, o protocolo e os
manifestos de execução preservam na própria árvore as evidências necessárias.
Uma cópia completa do histórico anterior permanece no backup local ignorado
`_local_git_backup/`. O repositório legado
`protasiofernando/projeto-mba-puc-rio` não é alterado por esta publicação.

## O que será publicado

- código mantido do pipeline e do dashboard;
- `formacao_portfolio/`, incluindo o snapshot byte a byte do método inicial;
- decisão curada, contrato de materialização e Stage 7 automático;
- projeção operacional agregada de 1.456 classificações;
- protocolo e código do estudo comparativo;
- `resultados_publicaveis/`, inclusive o dashboard estático autocontido;
- gerador code-only de uma base demonstrativa inteiramente artificial;
- documentação acadêmica, estado estruturado e apêndice de auditoria.

Não serão publicados CSVs, bancos, Stage 1, Stage 2, textos ou chaves de
chamados, classificações por chamado, checkpoints, `.env`, pacotes privados,
tarballs ou o workspace `_hpc/`. A base demonstrativa é produzida localmente
pelo avaliador e continua ignorada pelo Git.

## Gate obrigatório

Na raiz do projeto:

```powershell
python -m pytest -q
python scripts\validar_coerencia_projeto.py
python scripts\verificar_publicacao_novo_repo.py --full
git diff --check
git status --short
```

Os testes e os dois validadores precisam terminar em `PASS`; o comando de
whitespace não pode reportar erros. O `git status` deve mostrar somente as
alterações finais deliberadas.

O gate verifica o conjunto publicável, JSONs, links relativos, snapshot
histórico, resultados públicos, identidade do portfólio congelado e os 302
checks do Job 90. Ele não lê nem publica diretórios ignorados.

## Construção segura do commit-raiz

Depois do gate, as alterações são registradas localmente para produzir a árvore
final. Em seguida, cria-se um commit sem pai a partir dessa árvore, sem trocar a
branch de trabalho nem apagar o histórico local:

```powershell
git add -A
git commit -m "Consolida versão acadêmica e publicável do projeto"
$tree = git rev-parse 'HEAD^{tree}'
$rootCommit = git commit-tree $tree -m "Publica versão final do projeto MBA"
git rev-list --parents -n 1 $rootCommit
```

A última saída deve conter somente o hash de `$rootCommit`; um segundo hash
indicaria a presença indevida de um commit pai.

## Criação e primeiro envio

O destino é criado vazio, sem README, licença ou `.gitignore` adicionados pela
interface. Em seguida, configura-se um remote exclusivo e envia-se o
commit-raiz diretamente para `main`:

```powershell
gh repo create protasiofernando/mba-ia-puc --public --description "Projeto final do MBA em IA da PUC-Rio"
git remote add entrega https://github.com/protasiofernando/mba-ia-puc.git
git push entrega ${rootCommit}:refs/heads/main
git ls-remote --heads entrega
git ls-remote --tags entrega
```

O resultado esperado é uma única branch `main`, nenhuma tag e um commit-raiz
`entrega` aponta exclusivamente para o novo repositório, enquanto `origin` e
`publicacao` permanecem associados aos repositórios anteriores.

## Critério de pronto

- gate completo em `PASS`;
- apenas um commit alcançável a partir da `main` pública;
- somente a branch remota `main` e nenhuma tag;
- nenhum artefato sensível ou CSV no conjunto publicado;
- dashboard estático presente e autocontido;
- base artificial gerável por qualquer clone, sem insumo privado;
- formação do portfólio e comparação auditáveis a partir da árvore;
- nenhuma alegação de *ground truth* independente ou vencedor global único.
