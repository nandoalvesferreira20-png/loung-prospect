# Loung Leads - versão sem API paga

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

## 3. Rodar teste pequeno

```bash
python main.py --cidades Praia_Grande --segmentos clinica_odontologica --max 5 --output leads_teste.xlsx
```

## 4. Rodar com mais cidades

```bash
python main.py --cidades Praia_Grande Santos Sao_Vicente --segmentos clinica_odontologica clinica_medica consultorio_medico clinica_estetica --max 10 --output leads_loungtech.xlsx
```

## Observações

- Comece com `--max 5` para testar.
- Depois aumente aos poucos.
- Não use volumes muito altos de uma vez.
- O navegador abre visível por padrão para você acompanhar.
- Para rodar escondido, use `--headless`, mas recomendo deixar visível no início.