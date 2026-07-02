import os
import psycopg2
from psycopg2.extras import DictCursor
import re

# Load .env file manually if it exists
if os.path.exists(".env"):
    with open(".env") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                try:
                    key, value = line.strip().split("=", 1)
                    os.environ[key.strip()] = value.strip().strip('"').strip("'")
                except ValueError:
                    pass

# PostgreSQL database URL setup
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    pg_user = os.getenv("PGUSER", "postgres")
    pg_password = os.getenv("PGPASSWORD", "postgres")
    pg_host = os.getenv("PGHOST", "localhost")
    pg_port = os.getenv("PGPORT", "5432")
    pg_database = os.getenv("PGDATABASE", "hotel_booking")
    DATABASE_URL = f"postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_database}"

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

class ConnectionWrapper:
    def __init__(self, conn):
        self.conn = conn

    def cursor(self):
        return CursorWrapper(self.conn.cursor(cursor_factory=DictCursor))

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()

class CursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor
        self.last_inserted_id = None

    def execute(self, query, params=None):
        # 1. Translate SQL queries from SQLite syntax to PostgreSQL syntax
        # Replace SQLite AUTOINCREMENT with SERIAL for table creation
        query = re.sub(
            r'INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT', 
            'SERIAL PRIMARY KEY', 
            query, 
            flags=re.IGNORECASE
        )
        # Replace SQLite ? placeholder with PostgreSQL %s placeholder
        query = query.replace('?', '%s')
        
        # Execute query
        if params is None:
            self.cursor.execute(query)
        else:
            self.cursor.execute(query, params)
        
        # Capture lastrowid equivalent for INSERT statements
        if query.strip().upper().startswith("INSERT"):
            try:
                self.cursor.execute("SELECT LASTVAL()")
                self.last_inserted_id = self.cursor.fetchone()[0]
            except Exception:
                self.last_inserted_id = None

    def executemany(self, query, params_list):
        query = query.replace('?', '%s')
        self.cursor.executemany(query, params_list)

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        return RowWrapper(row)

    def fetchall(self):
        rows = self.cursor.fetchall()
        return [RowWrapper(r) for r in rows]

    @property
    def lastrowid(self):
        return self.last_inserted_id

    def close(self):
        self.cursor.close()

class RowWrapper:
    def __init__(self, row):
        self.row = row

    def __getitem__(self, key):
        return self.row[key]

    def keys(self):
        return self.row.keys()

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return ConnectionWrapper(conn)
