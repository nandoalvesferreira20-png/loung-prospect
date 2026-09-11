# Loung Prospect

## Prospecção Google Places → Carteira de Leads

Instale `requirements.txt` no ambiente da aplicação. Configure
`GOOGLE_PLACES_API_KEY` no ambiente ou no `.env` da raiz (sem versionar a chave).
O ambiente tem prioridade sobre `.env`; o carregamento é compartilhado com o script manual.

Execute `python main.py`, abra **Google Places API** na sidebar, preencha cidade,
segmento e quantidade (1–100, padrão 5) e clique em **Buscar e qualificar**.
A consulta pode consumir quota e paginar dentro do orçamento do provider.
Os leads são qualificados pelas regras existentes e salvos diretamente no SQLite.
Abra **Carteira de Leads**, ou use **Atualizar lista**, para ver as inserções.
A busca Playwright continua separada em **Buscar Leads**.

O banco recebe as colunas opcionais `provider` e `provider_place_id` por migração
idempotente, sem apagar dados. A inserção verifica duplicidade, na mesma transação,
por provider/Place ID, URI do Maps, empresa/endereço e empresa/telefone. Comparações
são exatas, ignoram componentes vazios e nunca usam apenas o nome. Registros
encontrados não são atualizados; IDs diferentes ainda podem coincidir por um critério
alternativo. Variações de grafia ou URL podem não ser reconhecidas como duplicatas.

Site preenchido é observado; site vazio continua não verificado. Telefone não é
copiado para WhatsApp. Contagens de qualificação incluem duplicatas recebidas;
inserções e duplicatas são contadas separadamente. Cada falha de qualificação ou
persistência é contabilizada sem impedir os demais leads.

Cancelar (ou sair da tela) solicita parada após a consulta completa do provider ou
entre leads. Não interrompe HTTP nem a paginação interna. Inserções já concluídas
são preservadas. Não há exportação Excel neste fluxo, atualização automática de
leads existentes ou retomada de sessão. A validação visual e a chamada real devem
ser feitas manualmente; os testes automatizados usam mocks e bancos temporários.

## Teste manual do Google Places (API real)

Este teste é optativo e pode consumir quota. Não faz parte do pytest.

1. Ative o ambiente: `.\.venv\Scripts\Activate.ps1`.
2. Instale as dependências de desenvolvimento: `python -m pip install -r requirements-dev.txt`.
3. Copie `.env.example` para `.env` e preencha a chave localmente. `.env` é ignorado pelo Git.
4. Execute `python scripts/test_google_places_real.py`.

O padrão é uma busca de até 5 dentistas em Taubaté. Para mudar:

```powershell
python scripts/test_google_places_real.py --city "Santos" --segment "veterinario" --limit 3
```

Alternativa sem `.env`, definindo a variável na sessão do PowerShell:

```powershell
$placesCredential = Read-Host "Chave Google Places" -AsSecureString
$env:GOOGLE_PLACES_API_KEY = [System.Net.NetworkCredential]::new('', $placesCredential).Password
python scripts/test_google_places_real.py
Remove-Item Env:GOOGLE_PLACES_API_KEY
```

A variável do ambiente tem prioridade sobre `.env`. O script permite limite de
1 a 20 e orçamento de uma requisição HTTP; se a API exigir página adicional,
reporta esgotamento do orçamento sem outra chamada. Não persiste resultados.
O provider lê o ambiente; script e serviço usam o mesmo carregador opcional de `.env`.

Essa versão usa Playwright para automatizar o navegador e coletar leads do Google Maps.

> Use com moderação. Não tente burlar captcha, bloqueios ou limites. Se o Google pedir verificação, pare e rode com volume menor depois.

## 1. Instalar dependências

```bash
pip install -r requirements.txt
```

## 2. Instalar o navegador do Playwright

```bash
python -m playwright install chromium
```

## 3. Abrir a interface gráfica

```bash
python main.py
```

Sem argumentos, somente a interface gráfica é executada. Fechar a janela encerra
o programa, sem iniciar a CLI.

## 4. Rodar teste pequeno pela CLI legada

Com argumentos, somente a CLI é executada, sem abrir a interface gráfica.
Os comandos e os formatos de saída `.xlsx` e `.csv` da CLI foram preservados.

```bash
python main.py --cidades Praia_Grande --segmentos clinica_odontologica --max 5 --output leads_teste.xlsx
```

## 5. Rodar com mais cidades pela CLI legada

```bash
python main.py --cidades Praia_Grande Santos Sao_Vicente --segmentos clinica_odontologica clinica_medica consultorio_medico clinica_estetica --max 10 --output leads_loungtech.xlsx
```

## Observações

- Comece com `--max 5` para testar.
- Depois aumente aos poucos.
- Não use volumes muito altos de uma vez.
- O navegador abre visível por padrão para você acompanhar.
- Para rodar escondido, use `--headless`, mas recomendo deixar visível no início.
