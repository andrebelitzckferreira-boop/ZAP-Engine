import json
from datetime import datetime, date
from .db import get_connection

def create_campaign(nome, mensagens_json, lote_tamanho, delay_lote_seg, delay_msg_seg,
                    media_url=None, media_type=None, daily_limit=0) -> int:
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO campaigns
           (nome, mensagens_json, lote_tamanho, delay_lote_seg, delay_msg_seg,
            media_url, media_type, daily_limit)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (nome, json.dumps(mensagens_json, ensure_ascii=False),
         lote_tamanho, delay_lote_seg, delay_msg_seg,
         media_url, media_type, daily_limit)
    )
    conn.commit()
    campaign_id = cursor.lastrowid
    conn.close()
    return campaign_id

def update_campaign_status(campaign_id, status):
    conn = get_connection()
    conn.execute("UPDATE campaigns SET status=? WHERE id=?", (status, campaign_id))
    conn.commit()
    conn.close()

def get_campaign(campaign_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM campaigns WHERE id=?", (campaign_id,)).fetchone()
    conn.close()
    return row

def list_campaigns():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM campaigns ORDER BY criado_em DESC").fetchall()
    conn.close()
    return rows

def log_message(campaign_id, contact_id, status, erro_msg=None):
    conn = get_connection()
    enviado_em = datetime.now().isoformat() if status == "enviado" else None
    conn.execute(
        """INSERT INTO messages_log (campaign_id, contact_id, status, erro_msg, enviado_em)
           VALUES (?, ?, ?, ?, ?)""",
        (campaign_id, contact_id, status, erro_msg, enviado_em)
    )
    conn.commit()
    conn.close()

def get_campaign_stats(campaign_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT status, COUNT(*) as total FROM messages_log WHERE campaign_id=? GROUP BY status",
        (campaign_id,)
    ).fetchall()
    conn.close()
    return {r["status"]: r["total"] for r in rows}

def get_antiban_settings():
    conn = get_connection()
    row = conn.execute("SELECT * FROM antiban_settings WHERE id=1").fetchone()
    conn.close()
    return dict(row) if row else {}

def save_antiban_settings(daily_limit, warmup_mode, warmup_day):
    conn = get_connection()
    conn.execute(
        """UPDATE antiban_settings SET daily_limit=?, warmup_mode=?, warmup_day=?,
           updated_em=CURRENT_TIMESTAMP WHERE id=1""",
        (daily_limit, 1 if warmup_mode else 0, warmup_day)
    )
    conn.commit()
    conn.close()

def get_today_count():
    today = date.today().isoformat()
    conn = get_connection()
    row = conn.execute("SELECT enviados FROM daily_counts WHERE data=?", (today,)).fetchone()
    conn.close()
    return row["enviados"] if row else 0

def increment_today_count():
    today = date.today().isoformat()
    conn = get_connection()
    conn.execute(
        "INSERT INTO daily_counts (data, enviados) VALUES (?,1) ON CONFLICT(data) DO UPDATE SET enviados=enviados+1",
        (today,)
    )
    conn.commit()
    conn.close()
