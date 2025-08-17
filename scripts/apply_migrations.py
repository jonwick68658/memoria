import os
import glob
import psycopg
from urllib.parse import urlparse

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("DATABASE_URL is required")

def apply_sql(conn, sql_text: str):
    with conn.cursor() as cur:
        cur.execute(sql_text)

def ensure_migrations_table(conn):
    with conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations(
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """)

def already_applied(conn, mig_id: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM schema_migrations WHERE version=%s", (mig_id,))
        return cur.fetchone() is not None

def mark_applied(conn, mig_id: str):
    with conn.cursor() as cur:
        cur.execute("INSERT INTO schema_migrations(version) VALUES(%s) ON CONFLICT DO NOTHING", (mig_id,))

def main():
    # psycopg3 connect
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        ensure_migrations_table(conn)
        migrations = sorted(glob.glob("db/migrations/*.sql"))
        for path in migrations:
            mig_id = os.path.basename(path)
            if already_applied(conn, mig_id):
                continue
            with open(path, "r", encoding="utf-8") as f:
                sql_text = f.read()
            apply_sql(conn, sql_text)
            mark_applied(conn, mig_id)
            print(f"Applied {mig_id}")

if __name__ == "__main__":
    main()