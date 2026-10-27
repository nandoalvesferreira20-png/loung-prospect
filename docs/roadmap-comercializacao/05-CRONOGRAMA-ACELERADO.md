# Cronograma acelerado e caminho crítico

Revisão: 23/10/2026. Dias úteis relativos D1–D10, sem presumir data de início, feriados ou disponibilidade contratada. Nenhuma execução autorizada por este documento.

## Esforço não é duração

Base dos 15 cartões de piloto: **160–288 horas-pessoa**. Desenvolvimento/infra/UX/integração: 116–216h; QA: 44–72h. Reserva de 20%: **192–346h**. Suposição de planejamento: quatro pessoas, 8h nominais/dia, mas **6h produtivas/pessoa/dia** para trabalho estimado; reuniões/contexto não podem ser contados como 8h de implementação contínua.

Capacidade bruta efetiva: 24h-pessoa/dia; 120h em 5 dias e 240h em 10. Dividir 160–288 por 24 produz só limite aritmético de 6,7–12 dias, sem dependências. Marwin sozinho tem 56–108h, equivalente a 9,3–18 dias; com reserva, aproximadamente 11,2–21,6 dias. Não é possível converter a folga frontend em paralelismo SQL imediato.

**5 dias: inviável para este escopo completo** (120h abaixo do mínimo 160h e caminho crítico maior). **10 dias: cenário otimista e condicional**, com esforço próximo ao limite inferior, decisões externas até D2, sem defeito importante ou nova exigência do cliente e dependências preparadas cedo. **Planejamento prudente: 12–22 dias úteis com reserva**, mais esperas externas não estimáveis. Não apresentar dez dias como compromisso garantido.

## Plano diário otimista de dez dias

Horas nas células são parte dos mínimos dos cartões, não horas extras. A soma é 160h; células de espera/reserva não são esforço executado prometido.

| Dia | Fernando | Laís | Miqueias | Marwin | Marco/condição |
|---|---|---|---|---|---|
| D1 | COM-01 6h: topologia e contratos | COM-11 4h: jornadas/estados | COM-03 6h: matriz e fixtures | COM-02 6h: catálogo/cópia/autoria | Baseline e contrato de piloto; confirmar carteira compartilhada e simultaneidade |
| D2 | COM-01 6h: BFF/TLS/sessão | COM-11 4h: estados/contexto | COM-03 6h: negativos/ACL | COM-02 2h + COM-05 4h | Integração auth/escrita em cópia; decisão externa requerida até D2 |
| D3 | COM-04 6h: evidência e decisão | COM-11 4h: configuração/limites | COM-03 4h: fechar evidências iniciais | COM-06 6h: quota/reserva | Se licença/escopo vetados ou não definidos, suspender previsão de D10 |
| D4 | COM-04 2h + COM-07 4h | COM-11 2h: integrar contrato SDR | COM-14 4h: gates e roteiro | COM-06 6h: concorrência/quota | Integração quota, contratos e configuração SDR |
| D5 | COM-07 4h + COM-10 2h | Reserva para retorno da integração | Reserva/revisão de evidências | COM-12 6h: readiness/conexões | UI/QA não precisam criar trabalho extra para ocupar horas |
| D6 | COM-10 6h: suspensão/estado | Reserva | COM-13 4h: harness/baseline | COM-12 6h: alerta/timeouts | API instrumentada para carga; política ativa/suspensa integrada |
| D7 | Reserva para correções de integração | Reserva | COM-13 6h: degraus/carga | COM-09 6h: retenção/export | Primeira evidência de capacidade; falha gera correção e novo prazo |
| D8 | Reserva | COM-11 2h: aceite final UI | COM-13 6h: soak/falhas/relatório | COM-09 6h: integridade/expiração | Envelope medido; revisão de dados; backlog corretivo se houver falhas |
| D9 | COM-15 4h: candidato/runbooks | Reserva/suporte de UX | COM-14 4h: E2E/candidato | COM-08 6h: restore isolado | Sem produção; backup/restore e cenário final precisam passar |
| D10 | COM-15 4h: handover/decisão | Reserva | COM-14 4h: regressão final e checklist | COM-08 2h: concluir restore | GO só com todos os gates; quatro horas restantes de Marwin não garantem absorver um incidente |

COM-03 tem evidência inicial D3 e acompanha regressão final em COM-14. COM-13 inicia preparação antes de concluir todos os componentes, mas o relatório final deve registrar versão/topologia e confirmar compatibilidade do candidato; qualquer mudança material após a carga exige repetir casos afetados. COM-11 só fecha no D8 após integrar configuração/estado. O restore D10 é um limite de saída: falha nele impede o piloto, mesmo que o cronograma esteja no último dia.

## Caminhos críticos

1. **Técnico:** baseline/schema → COM-02/05 → COM-06 → COM-12 → COM-13 → correções se necessárias → COM-14/15. Em paralelo no mesmo especialista: COM-09 e COM-08; ambas também impedem a liberação. Esse compartilhamento do recurso Marwin forma o maior gargalo.
2. **Dados/contrato:** decisão externa COM-04 → adequação COM-09/11 → testes de dados → liberação. Prazo externo sem limite assumido. Veto do uso Places exige novo escopo P0 fora desta estimativa.
3. **Produto:** oferta/identidade COM-07 + estado comercial COM-10 → UI COM-11 → E2E. Carteira privada por vendedor ou 100 operações caras simultâneas mudam esse caminho.

## Marcos de decisão e ajuste

- D1: confirmar simultaneidade alvo, volume esperado, privacidade da carteira, limites, responsável jurídico e acesso ao staging. Ausência dessas definições impede promessa de prazo.
- D2–3: catálogo/autoria e licença. Não tratar SQL existente como implantação concluída.
- D6: topologia, quota e observabilidade prontas para medição. Sem isso, carga não serve como aceite.
- D8: revisar capacidade real e requisitos. Se P95/erro/conexões falharem, promover correção mínima de COM-18 ou fila COM-17 quando comprovadamente necessária, com nova estimativa.
- D10: checklist e decisão registrada. Datas não substituem critérios de segurança.

## O que estende o prazo

Intervalo superior 288h por si só não cabe em dez dias de 240h efetivas. Marwin pode precisar de até 108h antes da reserva, equivalente a 18 dias produtivos; reserva leva a cerca de 22. Conformidade sem decisão, fornecedor alternativo, restrição por vendedor, fila distribuída, acesso indisponível e falhas graves de isolamento têm impacto adicional não quantificado. Não comprimir essas incertezas artificialmente em 5–10 dias.
