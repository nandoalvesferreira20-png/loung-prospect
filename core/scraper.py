# core/scraper.py

import time
from pathlib import Path
from typing import Callable

import pandas as pd
from playwright.sync_api import sync_playwright

from core.extractor import extract_company_data
from core.exporter import export_excel
from core.maps import collect_links
from core.qualification.service import qualify_records
from core.qualification.serialization import qualification_result_to_columns


def run_scraper(
    cidades: list[str],
    segmentos: list[str],
    max_results: int,
    output: str,
    headless: bool = False,
    log: Callable[[str], None] = print,
    on_progress: Callable[[int, int, str], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
    qualification_enabled: bool = False,
) -> dict:
    """
    Executa o processo completo de prospecção.

    Retorna um resumo com:
    - status;
    - leads encontrados;
    - quantidade processada;
    - quantidade de falhas;
    - tempo de execução;
    - caminho do arquivo.

    Quando habilitada, a qualificação acrescenta apenas a chave "qualificacoes":
    lista de {"registro": dict, "resultado": QualificationResult}, na ordem
    deduplicada. Acrescenta colunas derivadas ao Excel sem alterar campos originais.
    Leads já coletados
    também são qualificados após cancelamento; lote vazio não chama o serviço.
    Falhas individuais ficam no resultado, sem alterar os contadores de coleta.
    """

    on_progress = on_progress or (
        lambda processados, total, mensagem: None
    )

    should_stop = should_stop or (lambda: False)

    started_at = time.monotonic()

    rows: list[dict] = []
    tasks: list[dict] = []
    errors: list[dict] = []

    processed = 0
    stopped = False
    output_path = Path(output)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    log("🚀 Iniciando busca de leads...")

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                channel="chrome",
                headless=headless
            )

            context = browser.new_context(
                locale="pt-BR"
            )

            page = context.new_page()

            try:
                # =========================================
                # ETAPA 1 — Localizar empresas
                # =========================================

                for cidade in cidades:
                    if should_stop():
                        stopped = True
                        break

                    for segmento in segmentos:
                        if should_stop():
                            stopped = True
                            break

                        query = f"{segmento} em {cidade}"

                        log(f"🔍 Buscando: {query}")

                        try:
                            links = collect_links(
                                page=page,
                                query=query,
                                max_results=max_results,
                                log=log
                            )

                            log(
                                f"✅ {len(links)} empresas encontradas "
                                f"em '{query}'"
                            )

                            for link in links:
                                tasks.append({
                                    "link": link,
                                    "cidade": cidade,
                                    "segmento": segmento
                                })

                        except Exception as error:
                            errors.append({
                                "etapa": "busca",
                                "cidade": cidade,
                                "segmento": segmento,
                                "erro": str(error)
                            })

                            log(
                                f"❌ Erro ao buscar '{query}': "
                                f"{error}"
                            )

                # Remove links duplicados
                unique_tasks = []
                seen_links = set()

                for task in tasks:
                    link = task["link"]

                    if link in seen_links:
                        continue

                    seen_links.add(link)
                    unique_tasks.append(task)

                tasks = unique_tasks
                total = len(tasks)

                log(
                    f"📋 Total de empresas na fila: {total}"
                )

                on_progress(
                    0,
                    total,
                    "Empresas encontradas. Iniciando coleta..."
                )

                # =========================================
                # ETAPA 2 — Processar cada empresa
                # =========================================

                for task in tasks:
                    if should_stop():
                        stopped = True
                        log("⏹ Busca interrompida pelo usuário.")
                        break

                    link = task["link"]
                    cidade = task["cidade"]
                    segmento = task["segmento"]

                    current_position = processed + 1

                    message = (
                        f"Processando empresa "
                        f"{current_position} de {total}"
                    )

                    log(f"🔄 {message}")

                    on_progress(
                        processed,
                        total,
                        message
                    )

                    try:
                        page.goto(
                            link,
                            wait_until="domcontentloaded",
                            timeout=60000
                        )

                        page.wait_for_timeout(3000)

                        company = extract_company_data(
                            page=page,
                            cidade=cidade,
                            segmento=segmento
                        )

                        company_name = company.get(
                            "Empresa",
                            ""
                        ).strip()

                        if company_name:
                            rows.append(company)
                            log(f"✔ Lead salvo: {company_name}")

                        else:
                            errors.append({
                                "etapa": "extração",
                                "link": link,
                                "erro": "Nome da empresa não encontrado"
                            })

                            log(
                                "⚠ Empresa ignorada: "
                                "nome não encontrado."
                            )

                    except Exception as error:
                        errors.append({
                            "etapa": "processamento",
                            "link": link,
                            "cidade": cidade,
                            "segmento": segmento,
                            "erro": str(error)
                        })

                        log(
                            f"❌ Erro ao processar empresa: "
                            f"{error}"
                        )

                    finally:
                        processed += 1

                        on_progress(
                            processed,
                            total,
                            f"{processed} de {total} processadas"
                        )

                    # Pequena pausa entre empresas
                    for _ in range(10):
                        if should_stop():
                            stopped = True
                            break

                        time.sleep(0.1)

                    if stopped:
                        log("⏹ Encerrando processamento...")
                        break

            finally:
                context.close()
                browser.close()

    except Exception as error:
        errors.append({
            "etapa": "navegador",
            "erro": str(error)
        })

        log(f"❌ Erro geral no navegador: {error}")

    # =========================================
    # ETAPA 3 — Gerar arquivo
    # =========================================

    df = pd.DataFrame(rows)
    qualifications = []

    if not df.empty:
        df = df.drop_duplicates(
            subset=["Empresa", "Endereço"],
            keep="first"
        )

        export_df = df
        if qualification_enabled:
            records = df.to_dict(orient="records")
            results = qualify_records(records)
            qualifications = [
                {"registro": record, "resultado": result}
                for record, result in zip(records, results, strict=True)
            ]
            derived = pd.DataFrame(
                [qualification_result_to_columns(result) for result in results],
                index=df.index,
            )
            if set(df.columns) & set(derived.columns):
                raise ValueError("Qualification columns conflict with original columns")
            export_df = pd.concat([df, derived], axis=1)

        exported_path = export_excel(
            df=export_df,
            output=str(output_path),
            log=log
        )

        if exported_path:
            output_path = Path(exported_path)

        log(f"🎉 {len(df)} leads exportados.")

    else:
        log("⚠ Nenhum lead válido foi encontrado.")

    elapsed_seconds = time.monotonic() - started_at

    status = "cancelado" if stopped else "concluído"

    summary = {
        "status": status,
        "leads": len(df),
        "processados": processed,
        "total": len(tasks),
        "falhas": len(errors),
        "tempo_segundos": elapsed_seconds,
        "arquivo": str(output_path.resolve())
        if not df.empty
        else None,
        "erros": errors
    }

    if qualification_enabled:
        summary["qualificacoes"] = qualifications

    log(
        f"🏁 Processo {status}. "
        f"Leads: {summary['leads']} | "
        f"Falhas: {summary['falhas']} | "
        f"Tempo: {elapsed_seconds:.1f}s"
    )

    return summary

