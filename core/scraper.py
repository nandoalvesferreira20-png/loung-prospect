# core/scraper.py

import time
import os
from core.diagnostics import diagnostic_logging, trace
from pathlib import Path
from typing import Callable

import pandas as pd
from playwright.sync_api import sync_playwright

from core.extractor import extract_company_data
from core.exporter import export_excel
from core.maps import collect_links, iter_links
from core.lead_filter import DEFAULT_MIN_SCORE, WebsiteStatus, classificar_status_site, accepted_columns, new_search_stats, meets_min_score
from core.lead_filter import record_presence, is_without_own_website
from core.qualification.digital_presence import DigitalPresenceType
from core.validator import WEBSITE_VERIFICATION_KEY
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
    only_without_website: bool = False,
    min_score: int = DEFAULT_MIN_SCORE,
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

    only_without_website habilita uma meta TOTAL de max_results aceitos entre
    todas as cidades/segmentos. Exige ausência explicitamente inspecionada e score
    mínimo; qualifica durante a coleta, preservando V3 e o registro original.
    False mantém integralmente o contrato legado. A interface liga esse modo
    por padrão; chamadas Python antigas continuam com o comportamento anterior.
    """

    if only_without_website:
        if type(max_results) is not int or max_results < 1:
            raise ValueError("A meta deve ser um inteiro positivo.")
        if type(min_score) is not int or not 0 <= min_score <= 100:
            raise ValueError("Score mínimo deve ser inteiro entre 0 e 100.")
        qualification_enabled = True

    on_progress = on_progress or (
        lambda processados, total, mensagem: None
    )

    should_stop = should_stop or (lambda: False)

    started_at = time.monotonic()
    diagnostic_log = log if os.environ.get("LOUNG_WEBSITE_DEBUG") == "1" else None

    rows: list[dict] = []
    tasks: list[dict] = []
    errors: list[dict] = []

    processed = 0
    stopped = False
    stats = new_search_stats()
    accepted_results = []
    seen_companies = set()
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

                for cidade in ([] if only_without_website else cidades):
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
                processing_tasks = tasks
                if only_without_website:
                    search_page = context.new_page()
                    processing_tasks = _target_tasks(search_page, cidades, segmentos, tasks,
                                                     errors, stats, log, should_stop)
                    total = max_results

                log(
                    f"Meta: {max_results} leads sem site, score mínimo {min_score}"
                    if only_without_website else f"📋 Total de empresas na fila: {total}"
                )

                on_progress(
                    0,
                    total,
                    "Iniciando descoberta incremental de candidatos..." if only_without_website
                    else "Empresas encontradas. Iniciando coleta..."
                )

                # =========================================
                # ETAPA 2 — Processar cada empresa
                # =========================================

                for task in processing_tasks:
                    if should_stop():
                        stopped = True
                        log("⏹ Busca interrompida pelo usuário.")
                        break

                    link = task["link"]
                    cidade = task["cidade"]
                    segmento = task["segmento"]

                    current_position = processed + 1

                    message = (
                        f"[{len(rows)}/{max_results}] Analisando empresa {current_position}"
                        if only_without_website else f"Processando empresa {current_position} de {total}"
                    )

                    log(f"🔄 {message}")

                    on_progress(
                        len(rows) if only_without_website else processed,
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

                        with diagnostic_logging(diagnostic_log):
                            trace("SCRAPER_EXTRACT", url=link, verify_website=True)
                            company = extract_company_data(
                                page=page, cidade=cidade, segmento=segmento,
                                verify_website=True,
                            )
                            trace("EXTRACTED", company=company.get("Empresa"), site=company.get("Site"),
                                  verification=company.get(WEBSITE_VERIFICATION_KEY))

                        company_name = company.get(
                            "Empresa",
                            ""
                        ).strip()

                        if company_name:
                            if only_without_website:
                                identity = (company.get("Empresa"), company.get("Endereço"))
                                if identity in seen_companies:
                                    stats["duplicadas"] += 1
                                    stats["descartadas"] += 1
                                    log(f"Ignorando {company_name}: duplicada")
                                    continue
                                seen_companies.add(identity)
                                presence = record_presence(company)
                                if presence.presence_type == DigitalPresenceType.OWN_WEBSITE:
                                    stats["com_site"] += 1
                                    stats["descartadas"] += 1
                                    log(f"Ignorando {company_name}: possui site")
                                    continue
                                if not is_without_own_website(presence):
                                    stats["descartadas"] += 1
                                    log(f"Ignorando {company_name}: inspeção de site inconclusiva ou com erro")
                                    continue
                                stats["sem_site"] += 1
                                with diagnostic_logging(diagnostic_log):
                                    result = qualify_records([company])[0]
                                if not meets_min_score(result, min_score):
                                    stats["descartadas"] += 1
                                    log(f"Ignorando {company_name}: score insuficiente ou qualificação {result.status}")
                                    continue
                                accepted_results.append(result)
                                stats["qualificadas"] += 1
                            rows.append(company)
                            log(f"✔ Lead salvo: {company_name}")

                        else:
                            if only_without_website:
                                stats["descartadas"] += 1
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
                        if only_without_website:
                            stats["descartadas"] += 1
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
                        stats["analisadas"] = processed

                        on_progress(
                            len(rows) if only_without_website else processed,
                            total,
                            (f"[{len(rows)}/{max_results}] Leads aceitos | Analisadas: {processed} | "
                             f"Com site: {stats['com_site']} | Sem site: {stats['sem_site']} | "
                             f"Duplicadas: {stats['duplicadas']} | Descartadas: {stats['descartadas']}"
                             if only_without_website else f"{processed} de {total} processadas")
                        )

                    if only_without_website and len(rows) >= max_results:
                        break

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

    if only_without_website and should_stop():
        stopped = True

    # =========================================
    # ETAPA 3 — Gerar arquivo
    # =========================================

    df = pd.DataFrame([
        {key: value for key, value in row.items() if key != WEBSITE_VERIFICATION_KEY}
        for row in rows
    ])
    qualifications = []

    if not df.empty:
        df = df.drop_duplicates(
            subset=["Empresa", "Endereço"],
            keep="first"
        )

        export_df = df
        if qualification_enabled:
            records = df.to_dict(orient="records")
            for index, record in zip(df.index, records, strict=True):
                if WEBSITE_VERIFICATION_KEY in rows[index]:
                    record[WEBSITE_VERIFICATION_KEY] = rows[index][WEBSITE_VERIFICATION_KEY]
            with diagnostic_logging(diagnostic_log):
                for index, record in zip(df.index, records, strict=True):
                    trace("PRE_QUALIFY", row_index=int(index), company=record.get("Empresa"),
                          site=record.get("Site"), extracted_site=rows[index].get("Site"),
                          metadata_present=WEBSITE_VERIFICATION_KEY in record,
                          verification=record.get(WEBSITE_VERIFICATION_KEY))
                results = accepted_results if only_without_website else qualify_records(records)
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
            if only_without_website:
                extra = pd.DataFrame([accepted_columns(result, record_presence(record)) for record, result in zip(records, results, strict=True)], index=df.index)
                export_df = pd.concat([export_df, extra], axis=1)

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
        summary["qualification_summary"] = {
            "qualified": sum(item["resultado"].status == "qualified" for item in qualifications),
            "insufficient_data": sum(item["resultado"].status == "insufficient_data" for item in qualifications),
            "error": sum(item["resultado"].status == "error" for item in qualifications),
            "website_opportunities": sum(item["resultado"].opportunity == "website" for item in qualifications),
        }

    if only_without_website:
        summary["stats"] = stats
        summary["meta"] = max_results
        summary["min_score"] = min_score
        summary["motivo_parada"] = ("Cancelado pelo usuário" if stopped else
            "Meta atingida" if len(df) >= max_results else
            "Busca encerrada com falhas; consulte os erros" if errors else
            "Nenhum novo resultado disponível dentro dos limites de rolagem da busca")
        log(f"Meta: {max_results} | Encontrados: {len(df)} | Analisadas: {processed}. {summary['motivo_parada']}")

    log(
        f"🏁 Processo {status}. "
        f"Leads: {summary['leads']} | "
        f"Falhas: {summary['falhas']} | "
        f"Tempo: {elapsed_seconds:.1f}s"
    )

    return summary


def _target_tasks(page, cidades, segmentos, tasks, errors, stats, log, should_stop):
    """Lazy queue: keep search DOM separate from company inspection DOM."""
    seen = set()
    for cidade in cidades:
        for segmento in segmentos:
            if should_stop():
                return
            log(f"Buscando candidatos: {segmento} em {cidade}")
            try:
                for link in iter_links(page, f"{segmento} em {cidade}", log=log, should_stop=should_stop):
                    if should_stop():
                        return
                    if link in seen:
                        stats["duplicadas"] += 1
                        stats["descartadas"] += 1
                        continue
                    seen.add(link)
                    task = dict(link=link, cidade=cidade, segmento=segmento)
                    tasks.append(task)
                    yield task
            except Exception as error:
                errors.append(dict(etapa="busca", cidade=cidade, segmento=segmento, erro=str(error)))
                log(f"Erro na descoberta de links: {error}")

