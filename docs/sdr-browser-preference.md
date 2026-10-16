# Navegador para abrir o WhatsApp

O SDR oferece **Abrir WhatsApp com** no cabeçalho, com Navegador padrão do sistema,
Microsoft Edge e Google Chrome. Na primeira utilização, a opção é o navegador
padrão. Alterar o seletor salva a escolha e a aplica também aos leads já abertos.

## Persistência e abertura

Foi aproveitado `ui/settings.py`, que estava vazio, para implementar preferências
JSON por usuário. No Windows, o arquivo fica em
`%LOCALAPPDATA%\LoungProspect\settings.json`, com fallback para APPDATA e para o
perfil local caso as variáveis não existam. Não usa `.env`, o diretório da
instalação ou o banco de leads. A gravação é atômica e preserva outras chaves do
arquivo. Configuração ausente, inválida ou ilegível usa o navegador padrão.
Uma falha ao salvar é informada e a escolha continua válida durante a sessão.

Edge e Chrome são procurados no registro App Paths do usuário e da máquina,
nas visões de 32 e 64 bits, no PATH e nas instalações comuns sob LOCALAPPDATA,
PROGRAMFILES, PROGRAMFILES(X86) e PROGRAMW6432. Não há caminho específico do
computador de desenvolvimento.

O navegador padrão usa `webbrowser.open`. Edge/Chrome usam `subprocess.Popen`
com lista de argumentos e `shell=False`, mantendo a URL codificada como um
único argumento. A localização e a abertura ocorrem em worker; widgets e
confirmações são tratados na thread da interface. Falhas e timeout têm feedback,
sem registrar a URL ou o texto privado da mensagem.

Se o navegador não for encontrado, um diálogo oferece abrir pelo padrão.
Aceitar revalida o lead e o texto atuais antes de abrir. Recusar apenas mostra
a orientação para escolher outro navegador. O fallback não modifica a preferência
salva. A abertura não envia mensagens automaticamente.

## Arquivos desta implementação

- `ui/settings.py`: armazenamento por usuário e validação das três opções.
- `core/browser_launcher.py`: localização e abertura segura dos navegadores.
- `ui/browser_action.py`: abertura assíncrona, preferência e sinalização de navegador ausente.
- `ui/sales_workspace.py`: seletor compacto, gravação da escolha, fallback e feedback.
- `tests/test_browser_preferences.py`: regressões de configuração, localização e fallback.
- `tests/test_desktop_redesign.py`: ajuste do ponto de simulação do navegador padrão.
- `scripts/check_sdr_redesign_gui.py`: seletor, restauração e fallback no teste Tk real.
- `scripts/check_desktop_gui.py`, `scripts/check_sdr_gui.py`, `scripts/check_priority_gui.py`:
  preferências isoladas em pastas temporárias durante os testes.
- `docs/sdr-browser-preference.md`, `docs/sdr-inteligente.md`: documentação.

## Validação

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q --basetemp=tmp/pytest-browser-all
.\.venv\Scripts\python.exe -B -m pytest tests/test_browser_preferences.py tests/test_desktop_redesign.py tests/test_sdr_workspace_redesign.py -q --basetemp=tmp/pytest-browser-final
.\.venv\Scripts\python.exe -B scripts/check_sdr_redesign_gui.py
.\.venv\Scripts\python.exe -B scripts/check_desktop_gui.py
.\.venv\Scripts\python.exe -B scripts/check_sdr_gui.py --rows 197
.\.venv\Scripts\python.exe -B scripts/check_priority_gui.py
git diff --check
```

- Suíte completa: **960 testes passaram**; rodada direcionada final: **65 passaram**.
- Verificador SDR: seletor visível em 1050×650, 1280×760 e 1440×900, preferência
  restaurada após recriar a tela, abertura Edge/Chrome com argumentos simulados,
  fallback aceito/recusado e preferência preservada.
- Desktop: 14 combinações sem erros. SDR: três ciclos com 197 leads sem erros.
- Edge e Chrome foram localizados nesta máquina por uma consulta somente de leitura.

Os testes usam configurações e SQLite temporários e simulam as aberturas:
nenhum navegador ou conversa real foi aberto e nenhum lead ou preferência real
foi alterado. A geometria é verificada com Tk; não houve inspeção por captura.

## Teste manual

1. Abra o SDR e escolha uma das opções em Abrir WhatsApp com.
2. Selecione um lead, gere/abra e revise a mensagem, e clique em Abrir WhatsApp.
3. Feche e reabra o sistema: a escolha deve permanecer.
4. Em uma máquina sem o navegador escolhido, confira a oferta de abrir pelo
   padrão. O aceite vale somente para aquela abertura; a preferência permanece.
