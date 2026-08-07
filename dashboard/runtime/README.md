# Runtime local do dashboard

O arquivo `knowledge_base.db` é gerado localmente nesta pasta por
`scripts/knowledge_base.py`. Ele pode conter dados derivados dos chamados e é
ignorado pelo Git por `*.db`.

O dashboard continua funcional sem esse banco para as visões agregadas; abas
baseadas no histórico exigem sua geração local.
