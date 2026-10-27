"""Read existing schemas; save reviewed drafts using the shared write/backup guard."""
from contextlib import closing
from datetime import datetime, timezone
import sqlite3
import logging
import json
from fastapi import HTTPException
from core.sales.contact import blocked
from core.sales.models import validate_message
from core.database.lead_repository import FIELDS
from backend.repository import ReadRepository
from backend.prospecting.storage import StorageError

OUTREACH = {"id", "lead_id", "canal", "mensagem", "angulo", "confianca", "status",
            "criado_em", "atualizado_em", "provider", "model", "aprovado_em", "revisado_em"}
REVISIONS = {"id", "outreach_id", "lead_id", "mensagem", "status", "recorded_at"}


def compatible(connection):
    return all(required <= {r[1] for r in connection.execute(f"PRAGMA table_info({table})")}
               for table, required in (("outreach", OUTREACH), ("outreach_revisions", REVISIONS)))


class SdrStore:
    def __init__(self, selection_store):
        self.writer = selection_store
        self.reader = getattr(selection_store, "reader", None) or ReadRepository(selection_store.path)

    def lead(self, lead_id):
        with self.reader.connect() as (connection, _):
            row = connection.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "Lead não encontrado.")
            saved = None
            columns = {r[1] for r in connection.execute("PRAGMA table_info(lead_contact_preferences)")}
            if {"lead_id", "contact_type"} <= columns:
                preference = connection.execute("SELECT contact_type FROM lead_contact_preferences WHERE lead_id=?", (lead_id,)).fetchone()
                saved = preference[0] if preference else None
            lead = dict(row)
            # Old SQLite rows may contain NULL despite the desktop UI expecting text.
            lead["status"] = str(lead.get("status") or "")
            return lead, saved

    def history(self, lead_id):
        self.lead(lead_id)
        with self.reader.connect() as (connection, _):
            available = compatible(connection)
            lead_columns = {r[1] for r in connection.execute("PRAGMA table_info(leads)")}
            writable_schema = {*FIELDS, "id", "created_at", "updated_at"} <= lead_columns
            rows = connection.execute("SELECT id,mensagem,status,criado_em,atualizado_em,angulo FROM outreach WHERE lead_id=? ORDER BY criado_em DESC,id DESC LIMIT 50", (lead_id,)).fetchall() if available else []
        return {"available": available, "writesEnabled": self.writer.enabled and available and writable_schema,
                "reason": ("Histórico indisponível neste schema. A API não executa migrações." if not available else
                           "Salvamento indisponível neste schema legado. A API não executa migrações." if not writable_schema else
                           "Salvamento desabilitado: LOUNG_ENABLE_WRITES não está habilitado no backend." if not self.writer.enabled else None),
                "items": [{"id": r["id"], "message": r["mensagem"], "status": r["status"],
                           "createdAt": r["criado_em"], "updatedAt": r["atualizado_em"], "angle": r["angulo"]} for r in rows]}

    def save(self, draft, message, status):
        if not self.writer.enabled:
            raise HTTPException(403, "Salvamento desabilitado. A geração continua disponível sem permissão de escrita.")
        validate_message(message)
        try:
            with self.writer.lock:
                pending_backup = False
                with closing(self.writer.connect("rw")) as connection, connection:
                    connection.execute("BEGIN IMMEDIATE")
                    if not compatible(connection):
                        raise HTTPException(409, "Histórico incompatível. Nenhuma migração foi executada.")
                    lead = connection.execute("SELECT * FROM leads WHERE id=?", (draft["leadId"],)).fetchone()
                    if lead is None:
                        raise HTTPException(404, "Lead não encontrado.")
                    if blocked({**dict(lead), "status": str(lead["status"] or "")}):
                        raise HTTPException(409, "Lead bloqueado para novas abordagens.")
                    previous = connection.execute("SELECT * FROM outreach WHERE id=? AND lead_id=?", (draft.get("savedId"), draft["leadId"])).fetchone()
                    if previous and previous["mensagem"] == message and previous["status"] == status:
                        return previous["id"]
                    if previous and previous["status"] not in ("GERADA", "EDITADA"):
                        raise HTTPException(409, "Versão encerrada. Gere outra abordagem para preservar o histórico.")
                    if not self.writer.backed_up:
                        self.writer._backup()
                        pending_backup = True
                    now = datetime.now(timezone.utc).isoformat()
                    if previous:
                        connection.execute("INSERT INTO outreach_revisions (outreach_id,lead_id,mensagem,status,recorded_at) VALUES (?,?,?,?,?)",
                                           (previous["id"], draft["leadId"], previous["mensagem"], previous["status"], now))
                        connection.execute("UPDATE outreach SET mensagem=?,status=?,atualizado_em=?,aprovado_em=?,revisado_em=? WHERE id=? AND lead_id=?",
                                           (message, status, now, now if status == "APROVADA" else None, now, previous["id"], draft["leadId"]))
                        saved_id = previous["id"]
                    else:
                        saved_id = connection.execute("INSERT INTO outreach (lead_id,canal,mensagem,angulo,confianca,status,criado_em,atualizado_em,provider,model,aprovado_em,revisado_em) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                            (draft["leadId"], "whatsapp", message, draft["angle"], draft["confidence"], status, now, now,
                             draft["provider"], draft["model"], now if status == "APROVADA" else None, now)).lastrowid
                self.writer.backed_up = self.writer.backed_up or pending_backup
                draft["savedId"] = saved_id
                return saved_id
        except (sqlite3.Error, OSError, StorageError) as error:
            kinds = ('OperationalError', 'IntegrityError', 'DatabaseError', 'PermissionError', 'OSError', 'StorageError')
            kind = type(error).__name__
            logging.getLogger(__name__).warning(json.dumps({'event':'sdr.storage_failure',
                'endpoint':'/v1/sdr/history', 'http':503,
                'error_type':kind if kind in kinds else 'Error', 'code':'SDR_STORAGE_FAILED'}))
            raise HTTPException(503, "Não foi possível salvar. A transação foi revertida; verifique schema, bloqueios e backup.",
                                headers={'X-Loung-SDR-Code':'SDR_STORAGE_FAILED'}) from None
