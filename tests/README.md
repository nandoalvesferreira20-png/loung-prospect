# Testes de caracterização

Na raiz do projeto, em um ambiente virtual ativado:

```powershell
python -m pip install -r requirements-dev.txt
pytest
```

Não é necessário instalar os navegadores do Playwright. Os testes usam o pacote
Python para importar os módulos existentes, mas substituem o navegador e a busca
por mocks. A fixture automática bloqueia conexões de rede e a entrada no contexto
real do Playwright. Não há chamadas a páginas reais, nem abertura de Excel ou GUI.
Os arquivos Excel são reais, escritos apenas em diretórios temporários do pytest.
O relógio e as pausas do scraper são simulados.

## Cobertura

- Contrato atual de 13 colunas, na ordem existente, incluindo `Segmento`.
- Campos vazios, nome alternativo, valores do painel em português/inglês.
- Deduplicação executada pelo próprio scraper: URL e empresa/endereço.
- Exportação e leitura de Excel, sem índice adicional; erro de gravação propagado.
- Resumo, progresso final, fechamento dos recursos simulados e resultado vazio.
- Continuidade após erro em um lead ou uma busca; descarte de nome vazio.
- Cancelamento antes da busca e depois do primeiro lead, com exportação parcial.

## Comportamentos conhecidos, preservados intencionalmente

Estes testes descrevem o comportamento atual, não uma recomendação de negócio.
Ao corrigir um comportamento futuramente, atualizar seu teste explicitamente.

- Telefone é copiado para WhatsApp sem confirmação do canal.
- Falha de extração e ausência de informações podem produzir o mesmo registro
  vazio; `Site == ""` não comprova ausência de site.
- O extrator define `Status Comercial = Novo Lead`, `Próxima Ação = Qualificar
  lead`, potencial e observações vazios.
- O fallback usa o primeiro link externo aceito, mesmo que não seja um site da
  empresa.
- URLs repetidas preservam apenas o contexto da primeira busca.
- Nome/endereço iguais preservam o primeiro registro, inclusive com endereço
  vazio, podendo juntar empresas distintas.
- Erro ao iniciar o navegador ainda retorna `status = concluído`, com falha
  registrada e sem arquivo. Não é corrigido nesta etapa.

## Limites e próximos pontos de teste

Nenhum acoplamento impediu os cenários centrais: os símbolos importados pelo
scraper podem ser substituídos com monkeypatch, sem modificar produção.

- Seletores e rolagem reais do Maps: não verificados. Os locators do extrator são
  simulados; não garantem compatibilidade com o DOM atual. Uma evolução pequena
  seria testar `collect_links` com uma página falsa e cenários de rolagem.
- Cancelamento durante navegação/rolagem: não interrompe essas chamadas hoje;
  os testes cobrem os pontos em que o scraper consulta `should_stop`. Futuramente,
  propagar esse callback para `collect_links` permitiria testar parada interna.
- GUI, navegação entre telas e concorrência Tk: fora desta suíte. Separar o
  controle de execução dos widgets facilitaria testes de ciclo de vida; não foi
  feita essa mudança.
- Abertura de arquivo/pasta pelo Windows e navegador instalado: não testados.
  Podem receber testes com `os.startfile` simulado, sem alterar produção.
- CLI/coletor legado: não coberto nesta bateria; permanece preservado. Testes de
  roteamento com `gui_main` e `run` simulados podem ser adicionados sem refatoração.

## Verificações adicionais

```powershell
python -m compileall -q main.py app.py core ui tests
git diff --check
```
