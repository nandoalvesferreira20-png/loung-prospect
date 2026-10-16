"""One status, one next-action pointer, append-only desktop interaction history."""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import HTTPException
from core.commercial.values import STATUSES, commercial_status
from core.commercial.day import build_day
from core.database.interaction_repository import InteractionRepository
from core.database.lead_repository import FIELDS
from core.sales.contact import blocked
from backend.repository import ReadRepository
from backend.prospecting.storage import StorageError

INTERACTIONS = {"id", "lead_id", "tipo", "canal", "descricao", "created_at"}
CRM_FIELDS = {*FIELDS, "id", "created_at", "updated_at", "proximo_contato", "proxima_acao", "ultimo_contato", "observacoes"}


def revision(row):
    return hashlib.sha256(json.dumps(dict(row), sort_keys=True, default=str, ensure_ascii=True).encode()).hexdigest()


def columns(connection, table):
    # Only constant table names are passed here.
    return {r[1] for r in connection.execute(f"PRAGMA table_info({table})")}


def local_zone(name):
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, "Fuso horário inválido. Use um identificador IANA.") from None


class CrmService:
    def __init__(self, writer):
        self.writer = writer
        self.reader = ReadRepository(writer.path)

    @staticmethod
    def require_lead(connection, lead_id):
        row = connection.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Lead não encontrado.")
        return dict(row)

    def capabilities(self, connection):
        ready = CRM_FIELDS <= columns(connection, "leads") and INTERACTIONS <= columns(connection, "lead_interactions")
        return {"writesEnabled": self.writer.enabled and ready,
                "reason": "Schema comercial incompleto. A API não executa migrações; valide a atualização do desktop em uma cópia." if not ready else
                          "Edição desabilitada. Habilite LOUNG_ENABLE_WRITES no backend após validar uma cópia." if not self.writer.enabled else None}

    @staticmethod
    def stages(connection):
        saved = [r[0] for r in connection.execute("SELECT DISTINCT status FROM leads WHERE status IS NOT NULL AND status != '' ORDER BY status")]
        return list(dict.fromkeys([*STATUSES, *(commercial_status(s) for s in saved)]))

    @staticmethod
    def card(connection, row):
        row = dict(row)
        lead = ReadRepository.lead(row).model_dump()
        last = None
        activities, parameters = [], []
        if INTERACTIONS <= columns(connection, "lead_interactions"):
            activities.append("SELECT tipo AS kind,created_at AS at,id FROM lead_interactions WHERE lead_id=?")
            parameters.append(row["id"])
        outreach_columns = columns(connection,"outreach")
        if {"id","lead_id","status","criado_em"} <= outreach_columns:
            date = "COALESCE(atualizado_em,criado_em)" if "atualizado_em" in outreach_columns else "criado_em"
            activities.append(f"SELECT 'Abordagem · '||status,{date},id FROM outreach WHERE lead_id=?")
            parameters.append(row["id"])
        if activities:
            last = connection.execute("SELECT kind,at FROM (" + " UNION ALL ".join(activities) + ") ORDER BY julianday(at) DESC,id DESC LIMIT 1", parameters).fetchone()
        return {**lead, "revision": revision(row), "lastActivity": {"kind":last[0], "at":last[1]} if last else None,
                "lastContact":row.get("ultimo_contato"), "notes":row.get("observacoes"), "createdAt":row.get("created_at")}

    def detail(self, lead_id):
        with self.reader.connect() as (connection, _):
            row = self.require_lead(connection, lead_id)
            return {"lead":self.card(connection, row), "stages":self.stages(connection), **self.capabilities(connection)}

    def pipeline(self, q="", niche="", stage=None, offset=0, limit=8):
        with self.reader.connect() as (connection, lead_columns):
            stages = self.stages(connection)
            if stage is not None and stage not in stages and stage != "Não informado":
                raise HTTPException(422, "Etapa desconhecida.")
            filters, params = ["1=1"], []
            if q:
                filters.append("instr(fold(empresa),fold(?))>0")
                params.append(q)
            if niche and "segmento" in lead_columns:
                filters.append("fold(segmento)=fold(?)")
                params.append(niche)
            elif niche:
                filters.append("0=1")
            where = " AND ".join(filters)
            normalized = "COALESCE(NULLIF(commercial_status(status),''),'Não informado')"
            counts = {r[0]:r[1] for r in connection.execute(f"SELECT {normalized},count(*) FROM leads WHERE {where} GROUP BY {normalized}", params)}
            if "Não informado" in counts and "Não informado" not in stages:
                stages.append("Não informado")
            result = []
            for name in ([stage] if stage else stages):
                order = "qualification_score DESC,id ASC" if "qualification_score" in lead_columns else "id ASC"
                rows = connection.execute(f"SELECT * FROM leads WHERE {where} AND COALESCE(NULLIF(commercial_status(status),''),'Não informado')=? ORDER BY {order} LIMIT ? OFFSET ?", [*params, name, limit, offset]).fetchall()
                result.append({"stage":name, "total":counts.get(name, 0), "items":[self.card(connection, r) for r in rows], "offset":offset})
            niches = [r[0] for r in connection.execute("SELECT DISTINCT segmento FROM leads WHERE segmento IS NOT NULL AND segmento!='' ORDER BY segmento LIMIT 1000")] if "segmento" in lead_columns else []
            return {"columns":result, "stages":stages, "niches":niches, "total":sum(counts.values()), **self.capabilities(connection)}

    def activities(self, lead_id, offset=0, limit=20):
        with self.reader.connect() as (connection, _):
            row = self.require_lead(connection, lead_id)
            parts, args = [], []
            if row.get("created_at"):
                parts.append("SELECT ? AS id,? AS kind,? AS description,? AS at,'record' AS origin")
                args.extend(["created", "Lead criado", "Data de criação registrada na base.", row["created_at"]])
            if row.get("observacoes"):
                parts.append("SELECT ?,?,?,?,'record'")
                args.extend(["legacy-notes", "Observações da ficha", row["observacoes"], None])
            available = INTERACTIONS <= columns(connection, "lead_interactions")
            if available:
                parts.append("SELECT 'activity-'||id,tipo,descricao,created_at,CASE WHEN substr(tipo,1,6)='CRM · ' THEN 'manual' ELSE 'record' END FROM lead_interactions WHERE lead_id=?")
                args.append(lead_id)
            outreach_columns = columns(connection,"outreach")
            if {"id", "lead_id", "mensagem", "status", "criado_em"} <= outreach_columns:
                date = "COALESCE(atualizado_em,criado_em)" if "atualizado_em" in outreach_columns else "criado_em"
                parts.append(f"SELECT 'draft-'||id,'Abordagem · '||status,mensagem,{date},'draft' FROM outreach WHERE lead_id=?")
                args.append(lead_id)
            if {"id","lead_id","mensagem","status","recorded_at"} <= columns(connection,"outreach_revisions"):
                parts.append("SELECT 'revision-'||id,'Versão arquivada · '||status,mensagem,recorded_at,'draft' FROM outreach_revisions WHERE lead_id=?")
                args.append(lead_id)
            if not parts:
                return {"items":[], "total":0, "available":available}
            union = " UNION ALL ".join(parts)
            total = connection.execute(f"SELECT count(*) FROM ({union})", args).fetchone()[0]
            items = connection.execute(f"WITH events(id,kind,description,at,origin) AS ({union}) SELECT * FROM events ORDER BY julianday(at) DESC,id DESC LIMIT ? OFFSET ?", [*args, limit, offset]).fetchall()
            return {"items":[dict(r) for r in items], "total":total, "available":available}

    def mutate(self, lead_id, body, operation):
        if not self.writer.enabled:
            raise HTTPException(403, "Edição comercial desabilitada: LOUNG_ENABLE_WRITES não está habilitado.")
        try:
            with self.writer.lock:
                backup = False
                with closing(self.writer.connect("rw")) as connection, connection:
                    connection.execute("BEGIN IMMEDIATE")
                    if not self.capabilities(connection)["writesEnabled"]:
                        raise HTTPException(409, "Schema comercial incompleto. Nenhuma migração foi executada.")
                    row = self.require_lead(connection, lead_id)
                    if revision(row) != body.revision:
                        raise HTTPException(409, "O lead foi alterado em outra tela. Atualize os dados antes de tentar novamente.")
                    now = datetime.now(timezone.utc).isoformat()
                    updates, kind, description, channel = {}, "", "", "outro"
                    if operation == "stage":
                        if body.stage not in self.stages(connection):
                            raise HTTPException(422, "Etapa de destino inválida. Use uma etapa existente.")
                        if commercial_status(row["status"]) == body.stage:
                            return {"leadId":lead_id, "revision":revision(row), "changed":False}
                        if body.stage in ("Contato realizado","Fechado","Perdido") and not body.confirmed:
                            raise HTTPException(422, "Confirme explicitamente o contato, conversão ou perda antes de mudar para esta etapa.")
                        updates["status"] = body.stage
                        kind = "Etapa alterada"
                        if body.stage == "Contato realizado":
                            updates["ultimo_contato"] = now
                        description = f"Etapa anterior: {row['status']}; nova etapa: {body.stage}. Alteração confirmada manualmente; não comprova envio, resposta ou conversão por integração."
                    elif operation == "activity":
                        if body.kind != "Observação" and not body.confirmed:
                            raise HTTPException(422, "Confirme explicitamente que esta atividade ocorreu.")
                        if body.kind in ("Contato realizado", "Resposta recebida") and blocked({**row,"status":str(row.get("status") or "")}):
                            raise HTTPException(409, "Lead bloqueado para contato. Registre apenas observações sem reativar o contato.")
                        kind, description, channel = body.kind, body.description, body.channel
                        if kind == "Contato realizado":
                            updates["ultimo_contato"] = now
                    elif operation == "followup":
                        previous = f"Retorno anterior: {row.get('proximo_contato') or 'sem data'}; ação: {row.get('proxima_acao') or 'não informada'}."
                        if body.action == "complete":
                            if not (row.get("proximo_contato") or row.get("proxima_acao")):
                                raise HTTPException(409, "Este lead não possui retorno pendente.")
                            updates.update(proximo_contato=None, proxima_acao=None)
                            kind, description = "Follow-up concluído", previous + " Conclusão manual; não registra contato automaticamente."
                        else:
                            if not body.dueAt and not body.note.strip():
                                raise HTTPException(422, "Informe uma data ou a próxima ação para o retorno sem data.")
                            updates.update(proximo_contato=body.dueAt, proxima_acao=body.note.strip() or None)
                            kind = "Follow-up reagendado" if row.get("proximo_contato") or row.get("proxima_acao") else "Follow-up agendado"
                            description = previous + f" Próximo retorno: {body.dueAt or 'sem data'}; ação: {body.note.strip() or 'não informada'}."
                    if not self.writer.backed_up:
                        self.writer._backup()
                        backup = True
                    updates["updated_at"] = now
                    assignments = ",".join(f"{key}=?" for key in updates)  # keys are server-owned constants
                    connection.execute(f"UPDATE leads SET {assignments} WHERE id=?", [*updates.values(),lead_id])
                    InteractionRepository._insert(connection, lead_id, tipo="CRM · " + kind, canal=channel, descricao=description, created_at=now)
                    current = self.require_lead(connection, lead_id)
                self.writer.backed_up = self.writer.backed_up or backup
                return {"leadId":lead_id, "revision":revision(current), "changed":True}
        except (sqlite3.Error, OSError, StorageError):
            raise HTTPException(503, "Não foi possível salvar. A transação foi revertida; verifique bloqueios, schema e backup.") from None

    def followups(self, tz="America/Sao_Paulo", scope="pending", offset=0, limit=20):
        zone = local_zone(tz)
        reference = datetime.now(zone).date()
        with self.reader.connect() as (connection, lead_columns):
            if not {"proximo_contato", "proxima_acao"} <= lead_columns:
                return {"available":False,"items":[],"total":0,"invalidDates":0,**self.capabilities(connection)}
            rows = [dict(r) for r in connection.execute("SELECT * FROM leads")]
            for row in rows:
                try: row["qualification_score"] = int(row.get("qualification_score") or 0)
                except (ValueError, TypeError): row["qualification_score"] = 0
            summary = build_day(rows, reference, tz=zone)
            pending = [r for r in rows if r.get("proximo_contato") or r.get("proxima_acao")]
            if scope == "day":
                selected = summary.rows
            else:
                priority = {r["id"]:i for i,r in enumerate(summary.rows)}
                selected = sorted(pending, key=lambda r:(priority.get(r["id"],len(rows)),r.get("proximo_contato") or "z",r["id"]))
            items = []
            for row in selected[offset:offset+limit]:
                flags = build_day([row], reference, tz=zone).counts
                items.append({**self.card(connection,row),"overdue":bool(flags["atrasados"]),"today":bool(flags["hoje"]),
                              "hasFollowup":bool(row.get("proximo_contato") or row.get("proxima_acao"))})
            return {"available":True,"items":items,"total":len(selected),"pending":len(pending),
                    "overdue":summary.counts["atrasados"],"invalidDates":summary.invalid_dates,"referenceDate":str(reference),"timezone":tz,**self.capabilities(connection)}

    def metrics(self, tz="America/Sao_Paulo"):
        local_zone(tz)
        with self.reader.connect() as (connection, lead_columns):
            rows = [dict(r) for r in connection.execute("SELECT * FROM leads")]
            has_activities = INTERACTIONS <= columns(connection,"lead_interactions")
            contacts, responses = set(), set()
            if has_activities:
                contacts = {r[0] for r in connection.execute("SELECT DISTINCT lead_id FROM lead_interactions WHERE tipo IN ('CRM · Contato realizado','Primeiro contato')")}
                responses = {r[0] for r in connection.execute("SELECT DISTINCT lead_id FROM lead_interactions WHERE tipo='CRM · Resposta recebida'")}
                # Preserve explicit legacy facts when the lead advances. These
                # snapshots are server-authored stage events, never user notes.
                for lead_id, description in connection.execute("SELECT lead_id,descricao FROM lead_interactions WHERE tipo='CRM · Etapa alterada'"):
                    if any((description or "").startswith(f"Etapa anterior: {old}; nova etapa: ") for old in ("Contatado","Contato realizado")):
                        contacts.add(lead_id)
                    if (description or "").startswith("Etapa anterior: Respondeu; nova etapa: "):
                        responses.add(lead_id)
            existing_ids = {r["id"] for r in rows}
            for row in rows:
                if commercial_status(row["status"]) == "Contato realizado": contacts.add(row["id"])
                if row["status"] == "Respondeu": responses.add(row["id"])
                try:
                    if row.get("ultimo_contato") and datetime.fromisoformat(row["ultimo_contato"]).utcoffset() is not None:
                        contacts.add(row["id"])
                except (ValueError,TypeError): pass
            result = {"total":len(rows),"contacted":len(contacts & existing_ids) if has_activities or "ultimo_contato" in lead_columns else None,
                      "responded":len(responses & existing_ids) if has_activities else None,
                      "negotiations":sum(commercial_status(r["status"]) in ("Em conversa","Interessado","Proposta enviada") for r in rows),
                      "converted":sum(commercial_status(r["status"]) == "Fechado" for r in rows)}
        followups = self.followups(tz, limit=1)
        return {**result,"pending":followups.get("pending") if followups["available"] else None,
                "overdue":followups.get("overdue") if followups["available"] else None,
                "invalidDates":followups["invalidDates"]}
