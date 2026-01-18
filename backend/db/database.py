import sqlite3
import uuid
from pathlib import Path
from typing import Optional, Tuple
from pydantic import BaseModel

class Session(BaseModel):
    """Session model"""
    id: str
    name: str
    format: str
    tex_id: str | None = None
    pdf_id: str | None = None
    synctex_id: str | None = None


class DatabaseManager:
    def __init__(self, db_path: str = "db/sqlite.db", init: bool = False):
        """Initialize the database manager with the given database path."""
        self.db_path = Path(db_path)
        # Create the db directory if it doesn't exist
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if init:
            self.init_db()

    def get_connection(self):
        """Get a connection to the database."""
        return sqlite3.connect(self.db_path)

    def init_db(self):
        """Initialize the database with the session table."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DROP TABLE IF EXISTS sessions')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    format TEXT NOT NULL,
                    tex_id TEXT,
                    pdf_id TEXT,
                    synctex_id TEXT
                )
            ''')
            cursor.execute('DROP TABLE IF EXISTS resources')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS resources (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(id)
                )
            ''')
            conn.commit()

    def create_session(self, name: str, format: str) -> Session:
        """Create a new session record and return the session ID."""
        session_id = str(uuid.uuid4())

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO sessions (id, name, format) VALUES (?, ?, ?)",
                (session_id, name, format)
            )
            conn.commit()

        return Session(id=session_id, name=name, format=format)

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session record by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, format, tex_id, pdf_id, synctex_id FROM sessions WHERE id = ?",
                (session_id,)
            )
            row = cursor.fetchone()
            if row:
                return Session(
                    id=row[0],
                    name=row[1],
                    format=row[2],
                    tex_id=row[3],
                    pdf_id=row[4],
                    synctex_id=row[5]
                )
            return None

    def update_session(self, session_id: str, name: Optional[str] = None, format: Optional[str] = None, tex_id: Optional[str] = None, pdf_id: Optional[str] = None, synctex_id: Optional[str] = None) -> bool:
        """Update a session record. Returns True if the session was updated, False if not found."""
        session = self.get_session(session_id)
        if not session:
            return False

        # Use existing values if not provided
        current_name, current_format, current_tex, current_pdf, current_synctex = session.name, session.format, session.tex_id, session.pdf_id, session.synctex_id
        new_name = name if name is not None else current_name
        new_format = format if format is not None else current_format
        new_tex = tex_id if tex_id is not None else current_tex
        new_pdf = pdf_id if pdf_id is not None else current_pdf
        new_synctex = synctex_id if synctex_id is not None else current_synctex


        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE sessions SET name = ?, format = ?, tex_id = ?, pdf_id = ?, synctex_id = ? WHERE id = ?",
                (new_name, new_format, new_tex, new_pdf, new_synctex, session_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_session(self, session_id: str) -> bool:
        """Delete a session record. Returns True if deleted, False if not found."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
            return cursor.rowcount > 0

    def list_sessions(self) -> list[Session]:
        """Get all session records."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, format, tex_id, pdf_id, synctex_id FROM sessions")
            rows = cursor.fetchall()
            return [
                Session(
                    id=row[0],
                    name=row[1],
                    format=row[2],
                    tex_id=row[3],
                    pdf_id=row[4],
                    synctex_id=row[5]
                )
                for row in rows
            ]

    def add_resources(self, session_id: str, resource_ids: list[str]) -> None:
        """Add resource records associated with a session."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # TODO: optimize? this is still more than one query i think
            cursor.executemany(
                "INSERT INTO resources (id, session_id) VALUES (?, ?)",
                [(resource_id, session_id) for resource_id in resource_ids]
            )
            conn.commit()

    def list_resources(self, session_id: str) -> list[str]:
        """Get all resource IDs associated with a session."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM resources WHERE session_id = ?", (session_id,))
            rows = cursor.fetchall()
            return [row[0] for row in rows]


# Global instance for convenience
db_manager = DatabaseManager()


# Convenience functions that use the global instance
def create_session(name: str, format: str) -> Session:
    """Create a new session record and return the session ID."""
    return db_manager.create_session(name, format)


def get_session(session_id: str) -> Optional[Session]:
    """Get a session record by ID."""
    return db_manager.get_session(session_id)


def update_session(session_id: str, name: Optional[str] = None, format: Optional[str] = None, tex_id: Optional[str] = None, pdf_id: Optional[str] = None, synctex_id: Optional[str] = None) -> bool:
    """Update a session record. Returns True if the session was updated, False if not found."""
    return db_manager.update_session(session_id, name, format, tex_id, pdf_id, synctex_id)


def delete_session(session_id: str) -> bool:
    """Delete a session record. Returns True if deleted, False if not found."""
    return db_manager.delete_session(session_id)


def list_sessions() -> list[Session]:
    """Get all session records."""
    return db_manager.list_sessions()


def add_resources(session_id: str, resource_ids: list[str]) -> None:
    """Add resource records associated with a session."""
    return db_manager.add_resources(session_id, resource_ids)


def list_resources(session_id: str) -> list[str]:
    """Get all resource IDs associated with a session."""
    return db_manager.list_resources(session_id)