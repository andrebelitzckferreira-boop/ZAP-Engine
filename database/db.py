import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "disparo.db")

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            nome       TEXT,
            telefone   TEXT NOT NULL UNIQUE,
            status     TEXT DEFAULT 'pendente',
            criado_em  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nome            TEXT NOT NULL,
            mensagens_json  TEXT NOT NULL,
            media_url       TEXT,
            media_type      TEXT,
            lote_tamanho    INTEGER NOT NULL,
            delay_lote_seg  INTEGER NOT NULL,
            delay_msg_seg   INTEGER NOT NULL,
            daily_limit     INTEGER DEFAULT 0,
            status          TEXT DEFAULT 'pendente',
            criado_em       DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id  INTEGER NOT NULL,
            contact_id   INTEGER NOT NULL,
            status       TEXT DEFAULT 'pendente',
            erro_msg     TEXT,
            enviado_em   DATETIME,
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
            FOREIGN KEY (contact_id)  REFERENCES contacts(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS antiban_settings (
            id           INTEGER PRIMARY KEY DEFAULT 1,
            daily_limit  INTEGER DEFAULT 100,
            warmup_mode  INTEGER DEFAULT 0,
            warmup_day   INTEGER DEFAULT 1,
            updated_em   DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_counts (
            data       TEXT PRIMARY KEY,
            enviados   INTEGER DEFAULT 0
        )
    """)

    # Seed antiban settings
    cursor.execute("INSERT OR IGNORE INTO antiban_settings (id) VALUES (1)")
    conn.commit()
    conn.close()
    print("✅ Banco de dados inicializado.")

if __name__ == "__main__":
    init_db()
