# Publicação inicial e manutenção do repositório acadêmico

O repositório `protasiofernando/mba-ia-puc` foi criado em 7 de agosto de 2026 a
partir de uma árvore code-only validada, registrada em um commit-raiz sem herdar
os commits dos repositórios reaproveitados. Depois dessa consolidação inicial, a
`main` recebeu revisões acadêmicas e técnicas deliberadas. Esse histórico
posterior faz parte da auditabilidade e não deve ser zerado novamente.

O estado público esperado contém somente a branch `main` e a tag anotada
`formacao-a5576c8`. A tag torna verificável o commit histórico que originou o
candidato estatístico; não é uma branch de arquivo nem uma alternativa à
entrega vigente.

A auditabilidade metodológica não depende do histórico público anterior. O
snapshot imutável em `formacao_portfolio/`, seus hashes, o protocolo e os
manifestos de execução preservam na própria árvore as evidências necessárias.
Uma cópia completa do histórico anterior permanece no backup local ignorado
`_local_git_backup/`. O repositório legado
`protasiofernando/projeto-mba-puc-rio` não é alterado por esta publicação.

## O que compõe a publicação

- código mantido do pipeline e do dashboard;
- `formacao_portfolio/`, incluindo o snapshot byte a byte do método inicial;
- decisão curada, contrato de materialização e Estágio 7 automático;
- projeção operacional agregada de 1.456 classificações;
- protocolo e código do estudo comparativo;
- `resultados_publicaveis/`, inclusive o dashboard estático autocontido;
- gerador code-only de uma base demonstrativa inteiramente artificial;
- documentação acadêmica, estado estruturado e apêndice de auditoria.

Na `main` não são publicados CSVs, bancos, Estágio 1, Estágio 2, textos ou chaves de
chamados, classificações por chamado, checkpoints, `.env`, pacotes privados,
tarballs ou o workspace `_hpc/`. A base demonstrativa é produzida localmente
pelo avaliador e continua ignorada pelo Git.

A tag histórica `formacao-a5576c8` contém a exceção
`data_exemplo/Extracao_Jira_exemplo.csv`: 15 chamados inteiramente fictícios,
sem usuário, texto ou identificador real, documentados no próprio commit. Essa
exceção existe para preservar a proveniência byte a byte e é validada
explicitamente pelo gate; ela não autoriza CSV real em nenhuma ref.

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

O workflow `.github/workflows/quality.yml` repete o gate integral em cada push
ou pull request para a `main`, usando `requirements-dev.txt`.

O gate verifica o conjunto publicável, todas as branches e tags locais, chaves
JSON duplicadas, links relativos, snapshot
histórico, resultados públicos, identidade do portfólio congelado e os 302
checks do Job 90. Ele aceita somente a exceção sintética documentada na tag de
formação. Ele não lê nem publica diretórios ignorados.

## Registro da construção inicial do commit-raiz

Os comandos abaixo registram como a publicação inicial foi produzida. Não devem
ser repetidos sobre o repositório atual, pois isso apagaria o histórico legítimo
das revisões posteriores. Na ocasião, as alterações foram registradas
localmente e um commit sem pai foi criado a partir da árvore final:

```powershell
git add -A
git commit -m "Consolida versão acadêmica e publicável do projeto"
$tree = git rev-parse 'HEAD^{tree}'
$rootCommit = git commit-tree $tree -m "Publica versão final do projeto MBA"
git rev-list --parents -n 1 $rootCommit
```

A última saída deve conter somente o hash de `$rootCommit`; um segundo hash
indicaria a presença indevida de um commit pai.

## Registro da criação e do primeiro envio

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

Na publicação inicial, o resultado esperado era uma única branch `main` e um
commit-raiz. As revisões posteriores foram adicionadas normalmente, e a tag
anotada de formação foi publicada para tornar a linhagem verificável.
`entrega` aponta exclusivamente para o novo repositório, enquanto os remotes
reaproveitados permanecem associados aos repositórios anteriores.

## Critério de pronto vigente

- gate completo em `PASS`;
- histórico da `main` preservado, sem reescrita destrutiva;
- somente a branch remota `main` e a tag anotada `formacao-a5576c8`;
- nenhuma branch de arquivo;
- nenhum artefato sensível em qualquer ref e nenhum CSV fora da exceção
  sintética explicitamente validada;
- dashboard estático presente e autocontido;
- base artificial gerável por qualquer clone, sem insumo privado;
- formação do portfólio e comparação auditáveis a partir da árvore;
- nenhuma alegação de *ground truth* independente ou vencedor global único.
