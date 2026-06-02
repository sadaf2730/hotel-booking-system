import os
import sqlite3
import re

# Detect if we should use PostgreSQL (production) or SQLite (local)
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    import psycopg2
    from psycopg2.extras import DictCursor
    # Support connection strings starting with postgres:// (Heroku standard)
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
else:
    psycopg2 = None

class ConnectionWrapper:
    def __init__(self, conn, is_postgres=False):
        self.conn = conn
        self.is_postgres = is_postgres

    def cursor(self):
        if self.is_postgres:
            return CursorWrapper(self.conn.cursor(cursor_factory=DictCursor), is_postgres=True)
        else:
            return CursorWrapper(self.conn.cursor(), is_postgres=False)

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()

class CursorWrapper:
    def __init__(self, cursor, is_postgres=False):
        self.cursor = cursor
        self.is_postgres = is_postgres
        self.last_inserted_id = None

    def execute(self, query, params=None):
        if self.is_postgres:
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
            self.cursor.execute(query, params)
            
            # Capture lastrowid equivalent for INSERT statements
            if query.strip().upper().startswith("INSERT"):
                try:
                    self.cursor.execute("SELECT LASTVAL()")
                    self.last_inserted_id = self.cursor.fetchone()[0]
                except Exception:
                    self.last_inserted_id = None
        else:
            self.cursor.execute(query, params)

    def executemany(self, query, params_list):
        if self.is_postgres:
            query = query.replace('?', '%s')
            self.cursor.executemany(query, params_list)
        else:
            self.cursor.executemany(query, params_list)

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        return RowWrapper(row, self.is_postgres)

    def fetchall(self):
        rows = self.cursor.fetchall()
        return [RowWrapper(r, self.is_postgres) for r in rows]

    @property
    def lastrowid(self):
        if self.is_postgres:
            return self.last_inserted_id
        return self.cursor.lastrowid

    def close(self):
        self.cursor.close()

class RowWrapper:
    def __init__(self, row, is_postgres=False):
        self.row = row
        self.is_postgres = is_postgres

    def __getitem__(self, key):
        # Both sqlite3.Row and psycopg2.extras.DictCursor support string-based lookup
        return self.row[key]

    def keys(self):
        if self.is_postgres:
            return self.row.keys()
        else:
            return self.row.keys()

def get_db_connection():
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL)
        return ConnectionWrapper(conn, is_postgres=True)
    else:
        # Fallback to local SQLite database path from env or default
        db_path = os.getenv("DATABASE_PATH", "hotel_booking_system.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return ConnectionWrapper(conn, is_postgres=False)
