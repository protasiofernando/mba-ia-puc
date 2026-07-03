# Guia de Extração e Tratamento dos Dados do Jira

Os dados de entrada do pipeline são exportados do Jira e pré-processados antes de serem usados. O script `extracao/extrair_jira.py` realiza esse processamento.

---

## Passo 1 — Exportar o CSV do Jira

Acesse: `https://<url-do-jira>/issues/?jql=`

Use uma query como a do modelo abaixo no campo de pesquisa, uma por período (o Jira limita a 1.000 registros por exportação). Os filtros de exclusão retiram grupos de requisição e categorias que estão fora do escopo da área analisada — ajuste-os conforme o seu portfólio:

```
project = "<nome-do-projeto-no-jira>"
AND created >= "2024-01-01" AND created <= "2025-01-01"
AND "Grupo da Requisição" != "<grupo-fora-do-escopo>"
AND "Customer Request Type" != "<categoria-fora-do-escopo>"
```

Ajuste as datas conforme o período desejado. Exporte em **CSV** com:
- **Separador**: `^` (circunflexo)
- **Encoding**: UTF-8
- **Todos os campos** selecionados

Salve os arquivos com nomes iniciados por `Extracao_Jira` (underscores, sem espaços). O sufixo é livre e pode representar ano, período ou lote:
```
Extracao_Jira_2024.csv
Extracao_Jira_2025.csv
Extracao_Jira_2026.csv
Extracao_Jira_lote_extra.csv
```

---

## Passo 2 — Executar o script de tratamento

```bash
# Da raiz do projeto
python extracao/extrair_jira.py \
    --csvs "caminho/para/Extracao_Jira_2024.csv" \
           "caminho/para/Extracao_Jira_2025.csv" \
           "caminho/para/Extracao_Jira_2026.csv" \
    --saida   "Extracao_Jira.xlsx"
```

Se os CSVs estiverem na mesma pasta onde o script é executado, os argumentos são opcionais.

### O que o script faz

| Etapa | O que faz |
|-------|-----------|
| Leitura | Lê todos os CSVs informados ou descobertos automaticamente (sep `^`, UTF-8) e concatena em um único DataFrame |
| Simplificação | Renomeia `Campo personalizado (Motivo)` → `Motivo` (e similares) |
| Comentários | Filtra comentários humanos (ignora automato), consolida em `comentarios_usuarios`, conta em `qtd_interacoes` |
| Limpeza de texto | Normaliza quebras de linha, remove tokens Jira, mascara e-mails e padrões de servidor |
| Recorte | Seleciona as ~100 colunas relevantes das ~493 do CSV bruto |
| Tempo | Calcula `Tempo total conclusão` em horas (Resolvido − Criado) |
| Exportação | Salva `Extracao_Jira.xlsx` com os dados limpos |

---

## Passo 3 — Colocar os CSVs na pasta do pipeline

Os CSVs brutos devem estar disponíveis para o pipeline. Copie-os para a pasta `data/` do projeto no HPC:

```bash
scp Extracao_Jira*.csv <seu.usuario>@<head-node>:~/triagem-chamados/data/
```

> Os CSVs não devem ser versionados no git — contêm dados pessoais de usuários.

---

## Colunas obrigatórias para o pipeline

O `data_loader.py` espera estas colunas nos CSVs:

| Coluna | Usado para |
|--------|-----------|
| `Resumo` | Título do chamado — principal campo de análise |
| `Chave do item` | Identificador único |
| `Situação` | Status do chamado |
| `Responsável` | Analista responsável |
| `Solicitante` | Usuário que abriu o chamado |
| `Criado` | Data de abertura |
| `Resolvido` | Data de fechamento |
| `Descrição` | Corpo do chamado |
| `Customer Request Type` | Categoria atual — base do portfólio atual |
| `Comentário`, `Comentário.1`, ... | Histórico de interações |
| `qtd_interacoes` | Número de interações (gerado pelo script) |

---

## Separador `^`

O circunflexo foi escolhido como separador por não aparecer nos textos dos chamados, evitando quebras de parsing que aconteceriam com vírgula ou ponto-e-vírgula.
