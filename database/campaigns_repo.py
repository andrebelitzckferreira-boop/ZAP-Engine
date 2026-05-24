import json
from datetime import date, datetime

from config.settings import (
    DEFAULT_BATCH_PAUSE_MAX_SECONDS,
    DEFAULT_BATCH_PAUSE_MIN_SECONDS,
    DEFAULT_DAILY_LIMIT,
    DEFAULT_DELAY_MAX_SECONDS,
    DEFAULT_DELAY_MIN_SECONDS,
    DEFAULT_HOURLY_LIMIT,
    DUPLICATE_COOLDOWN_HOURS,
)
from .db import get_connection


def create_campaign(
    nome,
    mensagens_json,
    lote_tamanho,
    delay_lote_seg,
    delay_msg_seg,
    media_url=None,
    media_type=None,
    daily_limit=0,
    hourly_limit=None,
    delay_min_seg=None,
    delay_max_seg=None,
    pause_every=None,
    pause_min_seg=None,
    pause_max_seg=None,
    duplicate_cooldown_hours=None,
) -> int:
    conn = get_connection()
    try:
        payload = (
            nome,
            json.dumps(mensagens_json, ensure_ascii=False),
            lote_tamanho,
            delay_lote_seg,
            delay_msg_seg,
            media_url,
            media_type,
            daily_limit,
            hourly_limit or DEFAULT_HOURLY_LIMIT,
            delay_min_seg or DEFAULT_DELAY_MIN_SECONDS,
            delay_max_seg or DEFAULT_DELAY_MAX_SECONDS,
            pause_every or lote_tamanho,
            pause_min_seg or DEFAULT_BATCH_PAUSE_MIN_SECONDS,
            pause_max_seg or DEFAULT_BATCH_PAUSE_MAX_SECONDS,
            duplicate_cooldown_hours or DUPLICATE_COOLDOWN_HOURS,
        )
        if conn.postgres:
            cur = conn.execute(
                """INSERT INTO campaigns
                   (nome, mensagens_json, lote_tamanho, delay_lote_seg, delay_msg_seg,
                    media_url, media_type, daily_limit, hourly_limit, delay_min_seg,
                    delay_max_seg, pause_every, pause_min_seg, pause_max_seg,
                    duplicate_cooldown_hours)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   RETURNING id""",
                payload,
            )
            campaign_id = cur.fetchone()["id"]
        else:
            cur = conn.execute(
                """INSERT INTO campaigns
                   (nome, mensagens_json, lote_tamanho, delay_lote_seg, delay_msg_seg,
                    media_url, media_type, daily_limit, hourly_limit, delay_min_seg,
                    delay_max_seg, pause_every, pause_min_seg, pause_max_seg,
                    duplicate_cooldown_hours)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                payload,
            )
            campaign_id = cur.lastrowid
        conn.commit()
        return campaign_id
    finally:
        conn.close()


def update_campaign_status(campaign_id, status):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE campaigns SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, campaign_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_campaign(campaign_id):
    conn = get_connection()
    try:
        return conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
    finally:
        conn.close()


def list_campaigns():
    conn = get_connection()
    try:
        return conn.execute("SELECT * FROM campaigns ORDER BY criado_em DESC").fetchall()
    finally:
        conn.close()


def log_message(campaign_id, contact_id, status, erro_msg=None, mensagem=None):
    conn = get_connection()
    try:
        enviado_em = datetime.now().isoformat(sep=" ", timespec="seconds") if status == "enviado" else None
        conn.execute(
            """INSERT INTO messages_log
               (campaign_id, contact_id, status, mensagem, erro_msg, enviado_em)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (campaign_id, contact_id, status, mensagem, erro_msg, enviado_em),
        )
        conn.commit()
    finally:
        conn.close()


def get_campaign_stats(campaign_id):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT status, COUNT(*) as total FROM messages_log WHERE campaign_id = ? GROUP BY status",
            (campaign_id,),
        ).fetchall()
        return {r["status"]: r["total"] for r in rows}
    finally:
        conn.close()


def get_antiban_settings():
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM antiban_settings WHERE id = 1").fetchone()
        data = dict(row) if row else {}
    finally:
        conn.close()

    data.setdefault("daily_limit", DEFAULT_DAILY_LIMIT)
    data.setdefault("hourly_limit", DEFAULT_HOURLY_LIMIT)
    data.setdefault("delay_min_seg", DEFAULT_DELAY_MIN_SECONDS)
    data.setdefault("delay_max_seg", DEFAULT_DELAY_MAX_SECONDS)
    data.setdefault("pause_every", 10)
    data.setdefault("pause_min_seg", DEFAULT_BATCH_PAUSE_MIN_SECONDS)
    data.setdefault("pause_max_seg", DEFAULT_BATCH_PAUSE_MAX_SECONDS)
    data.setdefault("duplicate_cooldown_hours", DUPLICATE_COOLDOWN_HOURS)
    return data


def save_antiban_settings(
    daily_limit,
    warmup_mode,
    warmup_day,
    hourly_limit=None,
    delay_min_seg=None,
    delay_max_seg=None,
    pause_every=None,
    pause_min_seg=None,
    pause_max_seg=None,
    duplicate_cooldown_hours=None,
):
    current = get_antiban_settings()
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE antiban_settings
               SET daily_limit = ?, hourly_limit = ?, warmup_mode = ?, warmup_day = ?,
                   delay_min_seg = ?, delay_max_seg = ?, pause_every = ?,
                   pause_min_seg = ?, pause_max_seg = ?, duplicate_cooldown_hours = ?,
                   updated_em = CURRENT_TIMESTAMP
               WHERE id = 1""",
            (
                int(daily_limit or DEFAULT_DAILY_LIMIT),
                int(hourly_limit or current.get("hourly_limit") or DEFAULT_HOURLY_LIMIT),
                1 if warmup_mode else 0,
                int(warmup_day or 1),
                int(delay_min_seg or current.get("delay_min_seg") or DEFAULT_DELAY_MIN_SECONDS),
                int(delay_max_seg or current.get("delay_max_seg") or DEFAULT_DELAY_MAX_SECONDS),
                int(pause_every or current.get("pause_every") or 10),
                int(pause_min_seg or current.get("pause_min_seg") or DEFAULT_BATCH_PAUSE_MIN_SECONDS),
                int(pause_max_seg or current.get("pause_max_seg") or DEFAULT_BATCH_PAUSE_MAX_SECONDS),
                int(duplicate_cooldown_hours or current.get("duplicate_cooldown_hours") or DUPLICATE_COOLDOWN_HOURS),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_today_count():
    today = date.today().isoformat()
    conn = get_connection()
    try:
        row = conn.execute("SELECT enviados FROM daily_counts WHERE data = ?", (today,)).fetchone()
        return row["enviados"] if row else 0
    finally:
        conn.close()


def get_current_hour_count():
    hour_key = datetime.now().strftime("%Y-%m-%d %H")
    conn = get_connection()
    try:
        row = conn.execute("SELECT enviados FROM hourly_counts WHERE hora = ?", (hour_key,)).fetchone()
        return row["enviados"] if row else 0
    finally:
        conn.close()


def increment_today_count():
    today = date.today().isoformat()
    hour_key = datetime.now().strftime("%Y-%m-%d %H")
    conn = get_connection()
    try:
        if conn.postgres:
            conn.execute(
                """INSERT INTO daily_counts (data, enviados) VALUES (?, 1)
                   ON CONFLICT (data) DO UPDATE SET enviados = daily_counts.enviados + 1""",
                (today,),
            )
            conn.execute(
                """INSERT INTO hourly_counts (hora, enviados) VALUES (?, 1)
                   ON CONFLICT (hora) DO UPDATE SET enviados = hourly_counts.enviados + 1""",
                (hour_key,),
            )
        else:
            conn.execute(
                """INSERT INTO daily_counts (data, enviados) VALUES (?, 1)
                   ON CONFLICT(data) DO UPDATE SET enviados = enviados + 1""",
                (today,),
            )
            conn.execute(
                """INSERT INTO hourly_counts (hora, enviados) VALUES (?, 1)
                   ON CONFLICT(hora) DO UPDATE SET enviados = enviados + 1""",
                (hour_key,),
            )
        conn.commit()
    finally:
        conn.close()


def get_ai_settings():
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM ai_settings WHERE id = 1").fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def save_ai_settings(ativo, groq_api_key, prompt_sistema, palavras_humano):
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE ai_settings
               SET ativo = ?, groq_api_key = ?, prompt_sistema = ?,
                   palavras_humano = ?, updated_em = CURRENT_TIMESTAMP
               WHERE id = 1""",
            (1 if ativo else 0, groq_api_key or "", prompt_sistema or "", palavras_humano or "HUMANO"),
        )
        conn.commit()
    finally:
        conn.close()


def get_or_create_conversation(jid, nome=""):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM conversations WHERE jid = ?", (jid,)).fetchone()
        if not row:
            if conn.postgres:
                conn.execute(
                    """INSERT INTO conversations (jid, nome) VALUES (?, ?)
                       ON CONFLICT (jid) DO NOTHING""",
                    (jid, nome or ""),
                )
            else:
                conn.execute("INSERT OR IGNORE INTO conversations (jid, nome) VALUES (?, ?)", (jid, nome or ""))
            conn.commit()
            row = conn.execute("SELECT * FROM conversations WHERE jid = ?", (jid,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def update_conversation(jid, historico, modo_humano=None):
    conn = get_connection()
    try:
        if modo_humano is not None:
            conn.execute(
                """UPDATE conversations
                   SET historico_json = ?, modo_humano = ?, ultima_msg = CURRENT_TIMESTAMP
                   WHERE jid = ?""",
                (json.dumps(historico, ensure_ascii=False), 1 if modo_humano else 0, jid),
            )
        else:
            conn.execute(
                """UPDATE conversations
                   SET historico_json = ?, ultima_msg = CURRENT_TIMESTAMP
                   WHERE jid = ?""",
                (json.dumps(historico, ensure_ascii=False), jid),
            )
        conn.commit()
    finally:
        conn.close()


def list_conversations_ai():
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM conversations ORDER BY ultima_msg DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def set_modo_humano(jid, ativo):
    conn = get_connection()
    try:
        conn.execute("UPDATE conversations SET modo_humano = ? WHERE jid = ?", (1 if ativo else 0, jid))
        conn.commit()
    finally:
        conn.close()
