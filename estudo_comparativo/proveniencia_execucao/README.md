# Proveniência da decisão usada na execução

Esta pasta preserva os bytes de entradas que precisam continuar comparáveis ao
manifesto do pacote executado, mas cuja documentação canônica foi depois
corrigida e enriquecida.

`feedback_portfolio_executado.json.b64` codifica, sem perda, a cópia byte a byte
do arquivo fornecido ao estudo comparativo. O conteúdo decodificado possui
SHA-256
`7ffa42771809063994c2f37417306f264debbab137930a859520371bb6235f47`.
Seu comentário interno contém nomenclatura técnica antiga e descreve de forma
invertida a relação entre decisão e espelho analítico. Ele é evidência de
execução, não documentação vigente e não deve ser editado.

A versão humana canônica está em
`../../formacao_portfolio/decisao_curada/feedback_portfolio.json`. Além de
corrigir os dois campos explicativos iniciais, ela documenta posteriormente a
justificativa de consolidação e as categorias substituídas. Isso não altera a
projeção analítica usada no estudo. O gate
`../../scripts/validar_coerencia_projeto.py` verifica a integridade dos bytes
executados e que as duas versões projetam o mesmo alvo congelado. Para
reconstituir a evidência localmente, basta decodificar o arquivo base64; não é
necessário fazer isso para usar ou auditar o projeto.
