import json

from .db import get_connection


def _row_to_dict(row):
    return dict(row) if row else None


def create_outbound_message(
    telefone: str,
    mensagem: str = "",
    origin: str = "",
    provider_message_id: str = "",
    provider_status: str = "",
    remote_jid: str = "",
    provider_raw=None,
    last_error: str = "",
):
    conn = get_connection()
    try:
        raw_text = ""
        if provider_raw is not None:
            try:
                raw_text = json.dumps(provider_raw, ensure_ascii=False, default=str)
            except Exception:
                raw_text = str(provider_raw)
        if conn.postgres:
            cur = conn.execute(
                """INSERT INTO outbound_messages
                   (origin, telefone, remote_jid, provider_message_id, provider_status,
                    mensagem, provider_raw, last_error)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   RETURNING id""",
                (
                    origin or "",
                    telefone or "",
                    remote_jid or "",
                    provider_message_id or "",
                    provider_status or "",
                    mensagem or "",
                    raw_text,
                    last_error or "",
                ),
            )
            return cur.fetchone()["id"]
        cur = conn.execute(
            """INSERT INTO outbound_messages
               (origin, telefone, remote_jid, provider_message_id, provider_status,
                mensagem, provider_raw, last_error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                origin or "",
                telefone or "",
                remote_jid or "",
                provider_message_id or "",
                provider_status or "",
                mensagem or "",
                raw_text,
                last_error or "",
            ),
        )
        return cur.lastrowid
    finally:
        conn.commit()
        conn.close()


def update_outbound_message(
    provider_message_id: str,
    provider_status: str | None = None,
    remote_jid: str | None = None,
    provider_raw=None,
    last_error: str | None = None,
):
    if not provider_message_id:
        return False
    conn = get_connection()
    try:
        updates = ["updated_at = CURRENT_TIMESTAMP"]
        params = []
        if provider_status is not None:
            updates.append("provider_status = ?")
            params.append(provider_status or "")
        if remote_jid is not None:
            updates.append("remote_jid = ?")
            params.append(remote_jid or "")
        if provider_raw is not None:
            try:
                raw_text = json.dumps(provider_raw, ensure_ascii=False, default=str)
            except Exception:
                raw_text = str(provider_raw)
            updates.append("provider_raw = ?")
            params.append(raw_text)
        if last_error is not None:
            updates.append("last_error = ?")
            params.append(last_error or "")
        params.append(provider_message_id)
        conn.execute(
            f"UPDATE outbound_messages SET {', '.join(updates)} WHERE provider_message_id = ?",
            params,
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_latest_outbound_by_phone(telefone: str):
    conn = get_connection()
    try:
        phone = telefone or ""
        row = conn.execute(
            """SELECT * FROM outbound_messages
               WHERE telefone = ? OR remote_jid = ? OR remote_jid = ?
               ORDER BY id DESC LIMIT 1""",
            (phone, f"{phone}@s.whatsapp.net", f"{phone}@lid"),
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_outbound_by_message_id(provider_message_id: str):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM outbound_messages WHERE provider_message_id = ? ORDER BY id DESC LIMIT 1",
            (provider_message_id or "",),
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()
