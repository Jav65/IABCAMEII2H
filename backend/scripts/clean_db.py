#!/usr/bin/env python3
"""
Script to clean the database by dropping all tables.
"""

import sys
from pathlib import Path

from db import DatabaseManager


def clean_database():
    """Clean the database by dropping all tables."""
    print("Cleaning database...")
    
    # Initialize the database manager
    db = DatabaseManager()
    
    # Drop all tables
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DROP TABLE IF EXISTS session')
        conn.commit()
    
    print("Database cleaned successfully!")


if __name__ == "__main__":
    clean_database()