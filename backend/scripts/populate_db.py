#!/usr/bin/env python3
"""
Script to populate the database with the new schema.
"""

import sys
from pathlib import Path

from db.database import DatabaseManager


def populate_database():
    """Populate the database with the new schema."""
    print("Populating database with new schema...")
    
    # Initialize the database manager - this will create the table with the new schema
    db = DatabaseManager()
    
    # The init_db method already creates the table with the new schema
    # So we just need to ensure it's initialized
    db.init_db()
    
    print("Database populated with new schema successfully!")


if __name__ == "__main__":
    populate_database()