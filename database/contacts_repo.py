from datetime import datetime, timedelta

from .db import get_connection

VALID_STATUSES = {"pendente", "enviado", "respondeu", "erro", "ignorado"}


def normalize_status(status: str) -> str:
    status = (status or "pendente").strip().lower()
    return status if status in VALID_STATUSES else "pendente"


def insert_contact(
    nome: str,
    telefone: str,
    cidade: str = "",
    status: str = "pendente",
    observacoes: str = "",
) -> bool:
    conn = get_connection()
    try:
        status = normalize_status(status)
        if conn.postgres:
            cur = conn.execute(
                """INSERT INTO contacts (nome, telefone, cidade, status, observacoes)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT (telefone) DO NOTHING
                   RETURNING id""",
                (nome or "", telefone, cidade or "", status, observacoes or ""),
            )
            ok = cur.fetchone() is not None
        else:
            cur = conn.execute(
                """INSERT OR IGNORE INTO contacts
                   (nome, telefone, cidade, status, observacoes)
                   VALUES (?, ?, ?, ?, ?)""",
                (nome or "", telefone, cidade or "", status, observacoes or ""),
            )
            ok = cur.rowcount > 0
        conn.commit()
        return ok
    finally:
        conn.close()


def insert_contacts_bulk(contatos: list[dict]) -> tuple[int, int]:
    inseridos = duplicados = 0
    for contato in contatos:
        telefone = contato.get("telefone")
        if not telefone:
            duplicados += 1
            continue
        ok = insert_contact(
            contato.get("nome", ""),
            telefone,
            cidade=contato.get("cidade", ""),
            status=contato.get("status", "pendente"),
            observacoes=contato.get("observacoes", ""),
        )
        if ok:
            inseridos += 1
        else:
            duplicados += 1
    return inseridos, duplicados


def get_pending_contacts(limit: int | None = None) -> list:
    conn = get_connection()
    try:
        query = "SELECT * FROM contacts WHERE status = 'pendente' ORDER BY criado_em ASC"
        params = ()
        if limit:
            query += " LIMIT ?"
            params = (limit,)
        return conn.execute(query, params).fetchall()
    finally:
        conn.close()


def update_contact_status(contact_id: int, status: str, last_error: str | None = None):
    conn = get_connection()
    try:
        status = normalize_status(status)
        if status == "enviado":
            conn.execute(
                """UPDATE contacts
                   SET status = ?, last_sent_at = CURRENT_TIMESTAMP, last_error = NULL,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (status, contact_id),
            )
        elif last_error:
            conn.execute(
                """UPDATE contacts
                   SET status = ?, last_error = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (status, last_error[:500], contact_id),
            )
        else:
            conn.execute(
                "UPDATE contacts SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, contact_id),
            )
        conn.commit()
    finally:
        conn.close()


def update_contact_fields(contact_id: int, nome: str, telefone: str, status: str, cidade: str = "", observacoes: str = ""):
    conn = get_connection()
    try:
        if cidade is None or observacoes is None:
            current = conn.execute("SELECT cidade, observacoes FROM contacts WHERE id = ?", (contact_id,)).fetchone()
            if current:
                if cidade is None:
                    cidade = current["cidade"]
                if observacoes is None:
                    observacoes = current["observacoes"]
        conn.execute(
            """UPDATE contacts
               SET nome = ?, telefone = ?, status = ?, cidade = ?, observacoes = ?,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (nome or "", telefone, normalize_status(status), cidade or "", observacoes or "", contact_id),
        )
        conn.commit()
    finally:
        conn.close()


def delete_contact(contact_id: int):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
        conn.commit()
    finally:
        conn.close()


def list_contacts() -> list:
    conn = get_connection()
    try:
        return conn.execute("SELECT * FROM contacts ORDER BY criado_em DESC").fetchall()
    finally:
        conn.close()


def count_contacts_by_status() -> dict:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT status, COUNT(*) as total FROM contacts GROUP BY status").fetchall()
        counts = {r["status"]: r["total"] for r in rows}
        for status in VALID_STATUSES:
            counts.setdefault(status, 0)
        return counts
    finally:
        conn.close()


def _phone_variants(telefone: str) -> set[str]:
    digits = "".join(ch for ch in str(telefone or "") if ch.isdigit())
    variants = {digits}
    if digits.startswith("55"):
        sem55 = digits[2:]
        variants.add(sem55)
    else:
        sem55 = digits
        variants.add("55" + digits)
    if len(sem55) == 11 and sem55[2] == "9":
        variants.add(sem55[:2] + sem55[3:])
        variants.add("55" + sem55[:2] + sem55[3:])
    return {v for v in variants if v}


def mark_responded_by_phone(telefone: str) -> bool:
    variants = _phone_variants(telefone)
    if not variants:
        return False
    conn = get_connection()
    try:
        for variant in variants:
            cur = conn.execute(
                """UPDATE contacts
                   SET status = 'respondeu', updated_at = CURRENT_TIMESTAMP
                   WHERE telefone = ? AND status IN ('pendente', 'enviado', 'erro')""",
                (variant,),
            )
            if cur.rowcount:
                conn.commit()
                return True
        conn.commit()
        return False
    finally:
        conn.close()


def was_sent_recently(contact: dict, cooldown_hours: int) -> bool:
    data = dict(contact)
    if cooldown_hours <= 0 or not data.get("last_sent_at"):
        return False
    raw = str(data["last_sent_at"])
    try:
        sent_at = datetime.fromisoformat(raw.replace("T", " ").split(".")[0])
    except ValueError:
        return False
    return datetime.now() - sent_at < timedelta(hours=cooldown_hours)
