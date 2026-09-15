# Loung Prospect

> **Prospecção inteligente e gestão comercial de leads.**  
> Encontre empresas, qualifique oportunidades e organize sua operação comercial em um único lugar.

O **Loung Prospect** é uma aplicação desktop desenvolvida pela **Loung Tech** para centralizar o processo de prospecção comercial — desde a descoberta de novos negócios até o acompanhamento de contatos, follow-ups, reuniões e propostas.

A aplicação integra **Google Places**, qualificação automática, priorização comercial, SQLite e ferramentas de gestão de leads em uma interface construída com Python e CustomTkinter.

---

## ✦ Visão geral

O Loung Prospect foi criado para transformar uma busca simples por empresas em um fluxo comercial organizado.

```text
Google Places
      │
      ▼
  Prospecção
      │
      ▼
 Qualificação
      │
      ▼
Score e Prioridade
      │
      ▼
Carteira de Leads
      │
      ▼
Gestão Comercial
      │
      ├── WhatsApp
      ├── Telefone
      ├── Follow-up
      ├── Reunião
      └── Proposta
      │
      ▼
    Meu Dia
```

---

# ✦ Principais recursos

## Prospecção com Google Places

A aplicação permite pesquisar empresas diretamente pelo **Google Places API** utilizando:

- cidade;
- segmento;
- quantidade desejada de resultados.

Os leads encontrados podem conter:

- nome da empresa;
- cidade;
- segmento;
- telefone;
- website;
- endereço;
- avaliação;
- quantidade de avaliações;
- localização no Google Maps.

Após a coleta, os registros seguem automaticamente para qualificação e podem ser adicionados à Carteira de Leads.

---

## Qualificação automática

Cada lead passa pelo mecanismo de qualificação do Loung Prospect.

A análise utiliza os dados disponíveis para gerar:

- status de qualificação;
- score comercial;
- prioridade;
- oportunidade identificada;
- evidências;
- motivos;
- limitações;
- versão das regras utilizadas.

### Prioridades

Os leads são organizados em quatro níveis:

| Prioridade | Significado |
|---|---|
| **Alta** | Lead com sinais comerciais fortes |
| **Boa** | Lead interessante para abordagem |
| **Média** | Lead que pode ser trabalhado |
| **Baixa** | Menor prioridade no momento |

> O score representa **prioridade comercial**, não probabilidade de venda.

---

## Carteira de Leads

Os leads encontrados ficam disponíveis em uma carteira central para acompanhamento.

A Carteira permite:

- pesquisar empresas;
- filtrar leads;
- visualizar score e prioridade;
- definir responsável;
- atualizar status comercial;
- registrar observações;
- definir próxima ação;
- agendar próximo contato;
- copiar informações de contato;
- abrir websites;
- acessar a localização no Google Maps;
- consultar o histórico comercial.

---

## Gestão Comercial

Além de encontrar leads, o Loung Prospect permite acompanhar o relacionamento comercial com cada empresa.

O pipeline possui status como:

```text
Novo
  ↓
Contato realizado
  ↓
Em conversa
  ↓
Reunião agendada
  ↓
Proposta enviada
  ↓
Fechado
```

Também existem estados auxiliares:

- Não respondeu
- Retornar depois
- Sem interesse
- Perdido

Status legados já armazenados continuam sendo preservados.

---

## Histórico de interações

Cada contato pode ser registrado individualmente no histórico do lead.

Exemplos:

- primeiro contato;
- mensagem;
- ligação;
- follow-up;
- reunião;
- proposta;
- observação.

Exemplo:

```text
12/09/2026 · 14:30
WhatsApp · Primeiro contato

Enviei uma apresentação da Loung e solicitei
contato com o responsável.

────────────────────────────────────

13/09/2026 · 10:15
Telefone · Ligação

Responsável pediu retorno após as 14h.
```

As interações ficam armazenadas no SQLite e permanecem disponíveis após reiniciar a aplicação.

---

## Meu Dia

A tela **Meu Dia** transforma a carteira em uma rotina operacional.

Ela destaca:

- contatos atrasados;
- contatos previstos para hoje;
- novos leads;
- reuniões agendadas;
- propostas enviadas.

Assim, a equipe consegue abrir o Loung Prospect e identificar rapidamente quais oportunidades precisam de atenção.

---

## Exportação para Excel

Os resultados da prospecção via Google Places podem ser exportados para `.xlsx`.

Ao finalizar uma busca, a interface permite trabalhar os leads na Carteira e utilizar o arquivo gerado externamente quando necessário.

A aplicação também preserva os fluxos de exportação existentes da prospecção legada.

---

## Deduplicação

Para reduzir registros repetidos, a persistência verifica diferentes identificadores antes de inserir um novo lead.

A prioridade de identificação inclui:

1. provider + Place ID;
2. URI do Google Maps;
3. empresa + endereço;
4. empresa + telefone.

Componentes vazios não são utilizados como chave e o nome da empresa, sozinho, não é suficiente para considerar dois registros duplicados.

> Variações de grafia, telefone, endereço ou URL ainda podem representar o mesmo estabelecimento sem serem detectadas automaticamente.

---

# ✦ Interface

O Loung Prospect utiliza uma interface desktop desenvolvida com **CustomTkinter**, seguindo a identidade visual da Loung Tech.

As principais áreas são:

### Visão Geral

Resumo da operação e acesso rápido às principais funcionalidades.

### Prospecção

Busca, qualificação e armazenamento de novos leads através do Google Places.

### Carteira de Leads

Central para consulta e gestão dos leads encontrados.

### Meu Dia

Organização das ações comerciais, retornos, reuniões e propostas.

### Prototype Studio

Ferramentas auxiliares preservadas dentro da aplicação.

---

## Screenshots

> Adicione screenshots da aplicação em `docs/images/` para exibi-las aqui.

```text
docs/
└── images/
    ├── dashboard.png
    ├── prospecting.png
    ├── leads.png
    └── my-day.png
```

Depois, você pode habilitar as imagens abaixo:

<!--
### Visão Geral

![Visão Geral](docs/images/dashboard.png)

### Prospecção

![Prospecção](docs/images/prospecting.png)

### Carteira de Leads

![Carteira de Leads](docs/images/leads.png)

### Meu Dia

![Meu Dia](docs/images/my-day.png)
-->

---

# ✦ Tecnologias

### Aplicação

- Python
- CustomTkinter

### Persistência e dados

- SQLite
- Pandas
- OpenPyXL

### Prospecção

- Google Places API
- Playwright

### Qualidade

- Pytest

---

# ✦ Estrutura do projeto

O projeto separa interface, coleta, qualificação, persistência e gestão comercial.

```text
loung-prospect/
│
├── core/
│   ├── commercial/
│   ├── database/
│   ├── importers/
│   ├── providers/
│   ├── prospecting/
│   └── qualification/
│
├── ui/
│   ├── components/
│   ├── lead_workspace.py
│   ├── my_day.py
│   ├── places_search.py
│   └── ...
│
├── scripts/
├── tests/
├── data/
│
├── main.py
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

---

# ✦ Instalação

## 1. Clone o repositório

```bash
git clone https://github.com/nandoalvesferreira20-png/loung-prospect.git
cd loung-prospect
```

## 2. Crie um ambiente virtual

```bash
python -m venv .venv
```

### Windows PowerShell

```powershell
.\.venv\Scripts\Activate.ps1
```

## 3. Instale as dependências

```bash
python -m pip install -r requirements.txt
```

---

# ✦ Configuração do Google Places

Crie um arquivo `.env` na raiz do projeto.

Você pode utilizar `.env.example` como referência.

```env
GOOGLE_PLACES_API_KEY=sua_chave_aqui
```

O arquivo `.env` não deve ser versionado.

A variável definida diretamente no ambiente possui prioridade sobre o valor existente no `.env`.

---

# ✦ Executando a aplicação

Com o ambiente virtual ativo:

```bash
python main.py
```

Sem argumentos, o Loung Prospect inicia somente a interface gráfica.

Fechar a janela encerra a aplicação sem iniciar a CLI legada.

---

# ✦ Google Places

Na interface:

1. abra a área de prospecção com Google Places;
2. informe a cidade;
3. informe o segmento;
4. escolha a quantidade;
5. execute a busca;
6. aguarde a qualificação;
7. consulte os resultados;
8. abra a Carteira para trabalhar os leads.

A consulta pode consumir quota da API do Google Places.

A chave é carregada através de:

```text
GOOGLE_PLACES_API_KEY
```

e nunca deve ser adicionada diretamente ao código.

---

# ✦ Teste manual da API

Existe um script isolado para validar a configuração real do Google Places.

> Esse teste é opcional, realiza chamada real e pode consumir quota. Ele não faz parte da suíte automatizada.

Instale as dependências de desenvolvimento:

```powershell
python -m pip install -r requirements-dev.txt
```

Execute:

```powershell
python scripts/test_google_places_real.py
```

Por padrão, o script realiza uma busca pequena.

Também é possível informar os parâmetros:

```powershell
python scripts/test_google_places_real.py --city "Santos" --segment "veterinario" --limit 3
```

### Chave temporária no PowerShell

Também é possível fornecer a chave somente durante a sessão:

```powershell
$placesCredential = Read-Host "Chave Google Places" -AsSecureString
$env:GOOGLE_PLACES_API_KEY = [System.Net.NetworkCredential]::new('', $placesCredential).Password

python scripts/test_google_places_real.py

Remove-Item Env:GOOGLE_PLACES_API_KEY
```

O ambiente possui prioridade sobre `.env`.

---

# ✦ Prospecção legada com Playwright

O fluxo original de prospecção via Google Maps/Playwright continua disponível separadamente.

Instale o Chromium utilizado pelo Playwright:

```bash
python -m playwright install chromium
```

## Teste pequeno pela CLI

```bash
python main.py \
  --cidades Praia_Grande \
  --segmentos clinica_odontologica \
  --max 5 \
  --output leads_teste.xlsx
```

No PowerShell, o comando também pode ser executado em uma única linha:

```powershell
python main.py --cidades Praia_Grande --segmentos clinica_odontologica --max 5 --output leads_teste.xlsx
```

## Mais cidades e segmentos

```powershell
python main.py --cidades Praia_Grande Santos Sao_Vicente --segmentos clinica_odontologica clinica_medica consultorio_medico clinica_estetica --max 10 --output leads_loungtech.xlsx
```

Com argumentos, somente a CLI é executada e a interface gráfica não é aberta.

Os formatos `.xlsx` e `.csv` existentes continuam preservados.

> A automação deve ser utilizada de forma responsável. Não tente contornar CAPTCHA, verificações, bloqueios ou limites das plataformas utilizadas.

---

# ✦ Banco de dados

O Loung Prospect utiliza **SQLite** como armazenamento local.

O banco mantém informações relacionadas a:

- leads;
- origem/provider;
- qualificação;
- score;
- oportunidade;
- responsável;
- status comercial;
- observações;
- próxima ação;
- próximo contato;
- último contato;
- histórico de interações.

O schema utiliza atualizações aditivas e idempotentes para preservar bancos existentes.

---

# ✦ Persistência comercial

O histórico de interações é armazenado separadamente dos dados principais do lead.

Isso permite manter uma linha do tempo sem sobrescrever contatos anteriores.

Uma interação pode atualizar, de forma consistente:

- último contato;
- status;
- próxima ação;
- próximo contato;
- canal preferencial.

Falhas transacionais não devem deixar apenas parte da operação persistida.

---

# ✦ Cancelamento e falhas

O processamento foi projetado para preservar o trabalho já concluído.

Durante uma prospecção:

- falhas de um lead podem ser isoladas;
- erros de persistência são contabilizados;
- registros válidos anteriores são preservados;
- o cancelamento é cooperativo;
- operações HTTP em andamento não são interrompidas à força.

A aplicação não tenta ocultar falhas de configuração da API como resultados vazios.

---

# ✦ Testes

Execute toda a suíte:

```bash
python -m pytest
```

Para saída resumida:

```bash
python -m pytest -q
```

No Windows, caso seja necessário utilizar um diretório temporário local:

```powershell
python -m pytest -q -p no:cacheprovider --basetemp=.pytest_tmp
```

A suíte cobre diferentes áreas do projeto, incluindo:

- Google Places;
- providers;
- qualificação;
- regras comerciais;
- prospecção;
- banco SQLite;
- deduplicação;
- importação;
- exportação;
- Carteira de Leads;
- gestão comercial;
- histórico de interações;
- Meu Dia;
- helpers e ciclos da interface.

---

# ✦ Segurança e privacidade

Alguns princípios adotados pelo projeto:

- credenciais não são armazenadas diretamente no código;
- `.env` permanece fora do Git;
- valores SQL são parametrizados;
- dados comerciais são persistidos localmente;
- URLs são validadas antes de serem abertas pela interface;
- falhas são isoladas quando possível;
- o score não representa probabilidade de venda;
- a qualificação não representa autorização automática para contato.

O uso da aplicação deve respeitar a legislação aplicável e os termos das fontes e serviços utilizados.

---

# ✦ Roadmap

Possíveis evoluções futuras:

- enriquecimento de leads;
- descoberta de e-mails públicos;
- integração de e-mail;
- templates de abordagem;
- métricas de conversão;
- novas fontes de prospecção;
- automação de follow-ups;
- evolução do dashboard comercial;
- relatórios comerciais.

---

# ✦ Sobre a Loung Tech

O **Loung Prospect** é desenvolvido pela **Loung Tech**.

Criamos soluções digitais sob medida para transformar processos e negócios através da tecnologia.

### O que desenvolvemos

- Websites e landing pages
- Sistemas e plataformas
- Automações
- Integrações
- Ferramentas internas
- Soluções com IA

**Loung Tech**  
*Transformamos ideias em experiências digitais.*

---

## Licença

Projeto desenvolvido pela **Loung Tech**.

Consulte os termos de licença do repositório antes de utilizar, modificar ou distribuir o software.