# Abordagem Comercial V1

Nos detalhes de um lead, abra **Abordagem**, escolha canal, objetivo e tom,
e clique em **Gerar mensagem**. Revise e edite o texto antes de copiar.
**Gerar outra versão** percorre 0, 1, 2, 0; mudar a combinação reinicia em 0.
Gerar mensagem reinicia a versão. Uma nova geração substitui a edição atual.
Copiar usa o texto atual, inclusive edições manuais. Nenhuma ação envia contato,
altera status ou registra interação. Follow-up e reativação são escolhas humanas,
sem consulta ou inferência de histórico. Registre contatos realizados na aba Comercial.

## Contratos e implementação

`OutreachContext` é uma fotografia dos dados; `context_from_lead` mapeia a linha
da carteira sem alterá-la. `OutreachRequest` explicita canal, objetivo, tom e índice.
`TemplateOutreachGenerator.generate` devolve `OutreachResult`, com texto, escolhas,
ID estável e avisos. O protocolo `OutreachGenerator` permite trocar a implementação
futuramente; não existe implementação de IA ou transporte nesta versão.

As frases são compostas localmente por canal, objetivo, tom e variação, com vocabulário
para dentista, estética, veterinário, advogado, restaurante e fallback genérico.
Os IDs incluem essa combinação e `v1`. Não há chamadas externas ou dependências novas.
O responsável informado é usado como remetente; ausente ou indisponível, usa
`DEFAULT_SENDER = "Fernando"`. O construtor aceita outro `fallback_sender`.

Site, oportunidade, score e avaliações são preservados no contexto, mas não geram
diagnósticos, elogios, números ou alegações no texto. Não se afirma que houve análise,
conversa anterior, necessidade de site ou resultado comercial. Não há links automáticos.
Nomes são incorporados sem assumir o gênero da marca. Instagram omite cidade para
ser mais curto; telefone contém etapas de roteiro, inclusive encerramento respeitoso.

## Limites

WhatsApp recomenda 450 caracteres, Instagram 350. Acima disso há aviso, sem truncamento.
Dados textuais muito longos ou inadequados devem ser revisados por uma pessoa.
O texto digitado manualmente é livre: as garantias dos templates não validam edições.
O responsável deve ser conferido antes do contato; não há validação de identidade.
O rascunho vive somente no modal. Não existe persistência, envio ou atualização comercial.

Os testes são offline, com callbacks de UI simulados e SQLite temporário para verificar
ausência de mudanças no lead e no histórico. A revisão visual do modal fica para o
ambiente desktop real.
