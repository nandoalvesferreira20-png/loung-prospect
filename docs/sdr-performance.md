# Diagnóstico de abertura do SDR no Windows

## Causa reproduzida

Em `ui/sales_workspace.py`, a construção/listagem síncrona criava todos os cards.
Os callbacks `<Configure>` dos cards e do editor configuravam `wraplength`
novamente mesmo quando somente a altura mudava. O mesmo padrão existia no
SalesPanel. A alteração disparava mais layout e pintura de scrollbars.
O stack do processo travado mostrou chamadas reentrantes de
`CTkScrollbar._draw -> update_idletasks -> callback`.

A consulta ao banco real foi somente leitura: 197 leads, aproximadamente
7,9 ms. Nenhum dado foi alterado. A criação do provider Groq na abertura
consulta configuração local; não realiza HTTP. Não foi encontrada chamada
de geração ou teste de conexão automática nessa abertura.

## Correção

- Wrapping somente quando a largura lógica muda, com debounce de 80 ms.
- Inicialização/consulta do repository em worker, resultado entregue por fila.
- Filtros sobre snapshot local, com debounce; uma consulta por atualização.
- Página de 12 cards reutilizados, construídos em lotes de três.
- Cache limitado de editores limpos, preservando editores com trabalho pendente.
- Proteção contra abertura duplicada e cancelamento dos callbacks ao destruir.
- Inicialização do SalesAgent no worker de geração. Widgets só são atualizados
  pela thread do Tkinter. Timeout existente do provider foi preservado.

## Medições locais

Reprodução isolada com 197 leads sintéticos, CustomTkinter real e sem rede:

| Medida | Antes | Depois |
|---|---:|---:|
| Construtor da tela | 0,94 s | 0,10 s |
| Primeiro heartbeat após início do mainloop | 17,67 s | 0,148 s |
| Configurações de wraplength | 3.546 até watchdog | 24 |
| Encerramento agendado para quatro segundos | watchdog aos 25 s totais | normal |

Teste da aplicação completa, três ciclos: carregamentos com 197 leads em
1,619 / 1,332 / 1,532 s; com 1.000 leads em 1,853 / 1,598 / 1,337 s.
Sem erros de callback. O maior intervalo entre callbacks no roteiro foi
2,346 / 2,692 s respectivamente; o roteiro executa várias seleções e saves
no mesmo callback, portanto esses números não representam apenas abertura.
Não se afirma latência constante para toda interação ou tamanho de banco.

## Reproduzir offline

```powershell
.venv\Scripts\python.exe scripts/check_sdr_gui.py --rows 197
.venv\Scripts\python.exe scripts/check_sdr_gui.py --rows 1000 --show
```

Usa banco temporário, leads sintéticos, provider simulado e bloqueio de rede.
Verifica navegação repetida, paginação, filtros, seleção, retenção/edição de
rascunhos, geração simulada e preservação dos leads. Não modifica o banco real.
Sem `--show`, a janela real fica transparente durante a execução.

## Diagnóstico e validação manual

```powershell
$env:LOUNG_SDR_DEBUG = "1"
.venv\Scripts\python.exe main.py
```

Os logs no terminal registram etapas, tempos e contagens. Exceções de callback
registram tipo e localização, sem mensagem da exceção, dados de lead ou chave.
Para desativar: `Remove-Item Env:\LOUNG_SDR_DEBUG`.

1. Abrir SDR, voltar ao Dashboard e repetir três vezes, incluindo clique duplo.
2. Paginar, filtrar por texto/segmento/status e selecionar leads diferentes.
3. Editar um rascunho, trocar de lead e voltar; conferir retenção e salvamento.
4. Conferir mensagens existentes, status e controles de consentimento.
5. Se desejar validar a API real, solicitar geração explicitamente e conferir
   resultado/erro/timeout; não houve chamada real durante esta correção.
6. Conferir Carteira, busca e exportação habituais.

Os testes GUI automatizados usam Windows/Tk real com dados sintéticos. A
validação visual final com o banco e as condições reais do usuário continua
sendo complementar; a correção não apaga nem recria o banco existente.
