import sqlite3
import uuid
from pathlib import Path
from typing import Optional, Tuple


class DatabaseManager:
    def __init__(self, db_path: str = "db/sqlite.db"):
        """Initialize the database manager with the given database path."""
        self.db_path = Path(db_path)
        # Create the db directory if it doesn't exist
        self.db_path.parent.mkdir(exist_ok=True)
        self.init_db()

    def get_connection(self):
        """Get a connection to the database."""
        return sqlite3.connect(self.db_path)

    def init_db(self):
        """Initialize the database with the session table."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS session (
                    id TEXT PRIMARY KEY,
                    tex_filepath TEXT NOT NULL,
                    pdf_filepath TEXT NOT NULL
                )
            ''')
            conn.commit()

    def create_session(self, tex_filepath: str, pdf_filepath: str) -> str:
        """Create a new session record and return the session ID."""
        session_id = str(uuid.uuid4())
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO session (id, tex_filepath, pdf_filepath) VALUES (?, ?, ?)",
                (session_id, tex_filepath, pdf_filepath)
            )
            conn.commit()
        
        return session_id

    def get_session(self, session_id: str) -> Optional[Tuple[str, str, str]]:
        """Get a session record by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, tex_filepath, pdf_filepath FROM session WHERE id = ?",
                (session_id,)
            )
            return cursor.fetchone()

    def update_session(self, session_id: str, tex_filepath: Optional[str] = None, pdf_filepath: Optional[str] = None) -> bool:
        """Update a session record. Returns True if the session was updated, False if not found."""
        session = self.get_session(session_id)
        if not session:
            return False
        
        # Use existing values if not provided
        current_tex, current_pdf = session[1], session[2]
        new_tex = tex_filepath if tex_filepath is not None else current_tex
        new_pdf = pdf_filepath if pdf_filepath is not None else current_pdf
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE session SET tex_filepath = ?, pdf_filepath = ? WHERE id = ?",
                (new_tex, new_pdf, session_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_session(self, session_id: str) -> bool:
        """Delete a session record. Returns True if deleted, False if not found."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM session WHERE id = ?", (session_id,))
            conn.commit()
            return cursor.rowcount > 0

    def list_sessions(self) -> list:
        """Get all session records."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, tex_filepath, pdf_filepath FROM session")
            return cursor.fetchall()


# Global instance for convenience
db_manager = DatabaseManager()


# Convenience functions that use the global instance
def create_session(tex_filepath: str, pdf_filepath: str) -> str:
    """Create a new session record and return the session ID."""
    return db_manager.create_session(tex_filepath, pdf_filepath)


def get_session(session_id: str) -> Optional[Tuple[str, str, str]]:
    """Get a session record by ID."""
    return db_manager.get_session(session_id)


def update_session(session_id: str, tex_filepath: Optional[str] = None, pdf_filepath: Optional[str] = None) -> bool:
    """Update a session record. Returns True if the session was updated, False if not found."""
    return db_manager.update_session(session_id, tex_filepath, pdf_filepath)


def delete_session(session_id: str) -> bool:
    """Delete a session record. Returns True if deleted, False if not found."""
    return db_manager.delete_session(session_id)


def list_sessions() -> list:
    """Get all session records."""
    return db_manager.list_sessions()