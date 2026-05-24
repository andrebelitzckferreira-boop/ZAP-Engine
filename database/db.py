import os
import sqlite3
from urllib.parse import urlparse

from config.settings import DATABASE_URL, DB_PATH


def is_postgres() -> bool:
    if not DATABASE_URL:
        return False
    scheme = urlparse(DATABASE_URL).scheme.lower()
    return scheme in {"postgres", "postgresql"}


def _to_pg(sql: str) -> str:
    return sql.replace("?", "%s")


class DBConnection:
    def __init__(self, conn, postgres: bool = False):
        self._conn = conn
        self.postgres = postgres

    def execute(self, sql: str, params=()):
        if params is None:
            params = ()
        if self.postgres:
            return self._conn.execute(_to_pg(sql), params)
        return self._conn.execute(sql, params)

    def executemany(self, sql: str, seq_of_params):
        if self.postgres:
            return self._conn.executemany(_to_pg(sql), seq_of_params)
        return self._conn.executemany(sql, seq_of_params)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def cursor(self):
        return self._conn.cursor()


def get_connection() -> DBConnection:
    if is_postgres():
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("Instale psycopg[binary] para usar DATABASE_URL/Postgres.") from exc

        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        return DBConnection(conn, postgres=True)

    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return DBConnection(conn, postgres=False)


def _column_exists(conn: DBConnection, table: str, column: str) -> bool:
    if conn.postgres:
        row = conn.execute(
            """SELECT 1 FROM information_schema.columns
               WHERE table_name = ? AND column_name = ?""",
            (table, column),
        ).fetchone()
        return bool(row)

    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


def _add_column(conn: DBConnection, table: str, column: str, definition: str):
    if not _column_exists(conn, table, column):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _create_tables_sqlite(conn: DBConnection):
    conn.execute("""CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        telefone TEXT NOT NULL UNIQUE,
        cidade TEXT DEFAULT '',
        observacoes TEXT DEFAULT '',
        status TEXT DEFAULT 'pendente',
        last_sent_at DATETIME,
        last_error TEXT,
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        mensagens_json TEXT NOT NULL,
        media_url TEXT,
        media_type TEXT,
        lote_tamanho INTEGER NOT NULL,
        delay_lote_seg INTEGER NOT NULL,
        delay_msg_seg INTEGER NOT NULL,
        delay_min_seg INTEGER DEFAULT 18,
        delay_max_seg INTEGER DEFAULT 90,
        hourly_limit INTEGER DEFAULT 18,
        pause_every INTEGER DEFAULT 10,
        pause_min_seg INTEGER DEFAULT 420,
        pause_max_seg INTEGER DEFAULT 1800,
        duplicate_cooldown_hours INTEGER DEFAULT 72,
        daily_limit INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pendente',
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS messages_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id INTEGER NOT NULL,
        contact_id INTEGER NOT NULL,
        status TEXT DEFAULT 'pendente',
        mensagem TEXT,
        erro_msg TEXT,
        enviado_em DATETIME,
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
        FOREIGN KEY (contact_id) REFERENCES contacts(id)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS outbound_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        origin TEXT DEFAULT '',
        telefone TEXT NOT NULL,
        remote_jid TEXT DEFAULT '',
        provider_message_id TEXT DEFAULT '',
        provider_status TEXT DEFAULT '',
        mensagem TEXT DEFAULT '',
        provider_raw TEXT DEFAULT '',
        last_error TEXT DEFAULT '',
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS antiban_settings (
        id INTEGER PRIMARY KEY DEFAULT 1,
        daily_limit INTEGER DEFAULT 80,
        hourly_limit INTEGER DEFAULT 18,
        warmup_mode INTEGER DEFAULT 0,
        warmup_day INTEGER DEFAULT 1,
        delay_min_seg INTEGER DEFAULT 18,
        delay_max_seg INTEGER DEFAULT 90,
        pause_every INTEGER DEFAULT 10,
        pause_min_seg INTEGER DEFAULT 420,
        pause_max_seg INTEGER DEFAULT 1800,
        duplicate_cooldown_hours INTEGER DEFAULT 72,
        updated_em DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS daily_counts (
        data TEXT PRIMARY KEY,
        enviados INTEGER DEFAULT 0
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS hourly_counts (
        hora TEXT PRIMARY KEY,
        enviados INTEGER DEFAULT 0
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS ai_settings (
        id INTEGER PRIMARY KEY DEFAULT 1,
        ativo INTEGER DEFAULT 0,
        groq_api_key TEXT DEFAULT '',
        prompt_sistema TEXT DEFAULT '',
        palavras_humano TEXT DEFAULT 'HUMANO',
        updated_em DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        jid TEXT NOT NULL UNIQUE,
        nome TEXT DEFAULT '',
        historico_json TEXT DEFAULT '[]',
        modo_humano INTEGER DEFAULT 0,
        ultima_msg DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")


def _create_tables_postgres(conn: DBConnection):
    conn.execute("""CREATE TABLE IF NOT EXISTS contacts (
        id SERIAL PRIMARY KEY,
        nome TEXT,
        telefone TEXT NOT NULL UNIQUE,
        cidade TEXT DEFAULT '',
        observacoes TEXT DEFAULT '',
        status TEXT DEFAULT 'pendente',
        last_sent_at TIMESTAMP,
        last_error TEXT,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS campaigns (
        id SERIAL PRIMARY KEY,
        nome TEXT NOT NULL,
        mensagens_json TEXT NOT NULL,
        media_url TEXT,
        media_type TEXT,
        lote_tamanho INTEGER NOT NULL,
        delay_lote_seg INTEGER NOT NULL,
        delay_msg_seg INTEGER NOT NULL,
        delay_min_seg INTEGER DEFAULT 18,
        delay_max_seg INTEGER DEFAULT 90,
        hourly_limit INTEGER DEFAULT 18,
        pause_every INTEGER DEFAULT 10,
        pause_min_seg INTEGER DEFAULT 420,
        pause_max_seg INTEGER DEFAULT 1800,
        duplicate_cooldown_hours INTEGER DEFAULT 72,
        daily_limit INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pendente',
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS messages_log (
        id SERIAL PRIMARY KEY,
        campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
        contact_id INTEGER NOT NULL REFERENCES contacts(id),
        status TEXT DEFAULT 'pendente',
        mensagem TEXT,
        erro_msg TEXT,
        enviado_em TIMESTAMP,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS antiban_settings (
        id INTEGER PRIMARY KEY DEFAULT 1,
        daily_limit INTEGER DEFAULT 80,
        hourly_limit INTEGER DEFAULT 18,
        warmup_mode INTEGER DEFAULT 0,
        warmup_day INTEGER DEFAULT 1,
        delay_min_seg INTEGER DEFAULT 18,
        delay_max_seg INTEGER DEFAULT 90,
        pause_every INTEGER DEFAULT 10,
        pause_min_seg INTEGER DEFAULT 420,
        pause_max_seg INTEGER DEFAULT 1800,
        duplicate_cooldown_hours INTEGER DEFAULT 72,
        updated_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS daily_counts (
        data TEXT PRIMARY KEY,
        enviados INTEGER DEFAULT 0
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS hourly_counts (
        hora TEXT PRIMARY KEY,
        enviados INTEGER DEFAULT 0
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS ai_settings (
        id INTEGER PRIMARY KEY DEFAULT 1,
        ativo INTEGER DEFAULT 0,
        groq_api_key TEXT DEFAULT '',
        prompt_sistema TEXT DEFAULT '',
        palavras_humano TEXT DEFAULT 'HUMANO',
        updated_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS conversations (
        id SERIAL PRIMARY KEY,
        jid TEXT NOT NULL UNIQUE,
        nome TEXT DEFAULT '',
        historico_json TEXT DEFAULT '[]',
        modo_humano INTEGER DEFAULT 0,
        ultima_msg TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")


def _migrate_existing_schema(conn: DBConnection):
    text_def = "TEXT DEFAULT ''"
    dt_def = "TIMESTAMP" if conn.postgres else "DATETIME"
    created_def = f"{dt_def} DEFAULT CURRENT_TIMESTAMP" if conn.postgres else dt_def
    conn.execute("SELECT 1")

    for column, definition in {
        "cidade": text_def,
        "observacoes": text_def,
        "last_sent_at": dt_def,
        "last_error": "TEXT",
        "updated_at": created_def,
    }.items():
        _add_column(conn, "contacts", column, definition)

    for column, definition in {
        "delay_min_seg": "INTEGER DEFAULT 18",
        "delay_max_seg": "INTEGER DEFAULT 90",
        "hourly_limit": "INTEGER DEFAULT 18",
        "pause_every": "INTEGER DEFAULT 10",
        "pause_min_seg": "INTEGER DEFAULT 420",
        "pause_max_seg": "INTEGER DEFAULT 1800",
        "duplicate_cooldown_hours": "INTEGER DEFAULT 72",
        "updated_at": created_def,
    }.items():
        _add_column(conn, "campaigns", column, definition)

    for column, definition in {
        "mensagem": "TEXT",
        "criado_em": created_def,
    }.items():
        _add_column(conn, "messages_log", column, definition)

    for column, definition in {
        "origin": "TEXT DEFAULT ''",
        "telefone": "TEXT NOT NULL DEFAULT ''",
        "remote_jid": "TEXT DEFAULT ''",
        "provider_message_id": "TEXT DEFAULT ''",
        "provider_status": "TEXT DEFAULT ''",
        "provider_raw": "TEXT DEFAULT ''",
        "last_error": "TEXT DEFAULT ''",
        "updated_at": created_def,
    }.items():
        _add_column(conn, "outbound_messages", column, definition)

    for column, definition in {
        "hourly_limit": "INTEGER DEFAULT 18",
        "delay_min_seg": "INTEGER DEFAULT 18",
        "delay_max_seg": "INTEGER DEFAULT 90",
        "pause_every": "INTEGER DEFAULT 10",
        "pause_min_seg": "INTEGER DEFAULT 420",
        "pause_max_seg": "INTEGER DEFAULT 1800",
        "duplicate_cooldown_hours": "INTEGER DEFAULT 72",
    }.items():
        _add_column(conn, "antiban_settings", column, definition)


def init_db():
    conn = get_connection()
    try:
        if conn.postgres:
            _create_tables_postgres(conn)
        else:
            _create_tables_sqlite(conn)
        _migrate_existing_schema(conn)
        if conn.postgres:
            conn.execute("INSERT INTO antiban_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING")
            conn.execute("INSERT INTO ai_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING")
        else:
            conn.execute("INSERT OR IGNORE INTO antiban_settings (id) VALUES (1)")
            conn.execute("INSERT OR IGNORE INTO ai_settings (id) VALUES (1)")
        conn.commit()
    finally:
        conn.close()
    print("Banco de dados inicializado.")


if __name__ == "__main__":
    init_db()
