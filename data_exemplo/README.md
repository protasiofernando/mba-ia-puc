# Base sintética de exemplo

`Extracao_Jira_exemplo.csv` contém **15 chamados fictícios** com o mesmo schema
operacional dos CSVs reais exportados do Jira (separador `^`, encoding UTF-8,
colunas que o `data_loader.py` consome). Nenhum dado real de usuário está presente:
nomes, códigos de acesso, servidores e datas são inventados.

A base existe para que qualquer pessoa que clone o repositório consiga executar
as análises sem acesso aos dados reais (que não são versionados por conterem
dados pessoais). Exemplo:

```bash
# Análise do ganho de tempo: resolução direta vs múltiplas interações
python analise_tempo_interacoes.py --dados data_exemplo
```

A composição reproduz o fenômeno observado na base real: os chamados abertos com
informações completas (resolvidos com até 1 interação) têm tempo de resolução
bem menor do que os que exigiram múltiplas trocas com o solicitante para
esclarecer o pedido.

| Grupo | Chamados | Perfil |
|-------|----------|--------|
| Resolução direta (≤1 interação) | EX-001 a EX-008 | Pedido completo na abertura; resolução em ~1–3 dias |
| Múltiplas interações (≥2) | EX-009 a EX-015 | Descrição insuficiente; idas e vindas; resolução em ~4–6 dias |
