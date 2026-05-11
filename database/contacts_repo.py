# =============================================================
# database/contacts_repo.py — CRUD de contatos
# =============================================================
from .db import get_connection


def insert_contact(nome: str, telefone: str) -> bool:
    """Insere um contato. Retorna True se inserido, False se já existia."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO contacts (nome, telefone) VALUES (?, ?)",
            (nome, telefone)
        )
        conn.commit()
        return True
    except Exception:
        return False   # telefone duplicado
    finally:
        conn.close()


def insert_contacts_bulk(contatos: list[dict]) -> tuple[int, int]:
    """
    Insere uma lista de dicts {'nome': ..., 'telefone': ...}.
    Retorna (inseridos, duplicados).
    """
    inseridos = duplicados = 0
    for c in contatos:
        ok = insert_contact(c.get("nome", ""), c["telefone"])
        if ok:
            inseridos += 1
        else:
            duplicados += 1
    return inseridos, duplicados


def get_pending_contacts(limit: int = None) -> list:
    """Retorna contatos com status 'pendente'."""
    conn = get_connection()
    query = "SELECT * FROM contacts WHERE status = 'pendente'"
    if limit:
        query += f" LIMIT {limit}"
    rows = conn.execute(query).fetchall()
    conn.close()
    return rows


def update_contact_status(contact_id: int, status: str):
    conn = get_connection()
    conn.execute(
        "UPDATE contacts SET status = ? WHERE id = ?",
        (status, contact_id)
    )
    conn.commit()
    conn.close()


def count_contacts_by_status() -> dict:
    conn = get_connection()
    rows = conn.execute(
        "SELECT status, COUNT(*) as total FROM contacts GROUP BY status"
    ).fetchall()
    conn.close()
    return {r["status"]: r["total"] for r in rows}
