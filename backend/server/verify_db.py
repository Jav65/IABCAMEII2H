#!/usr/bin/env python3
"""
Verify the database table structure.
"""

import sqlite3
from pathlib import Path

# Connect to the database
db_path = Path("db/sqlite.db")
conn = sqlite3.connect(db_path)

# Query the table information
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(session)")
table_info = cursor.fetchall()

print("Table 'session' structure:")
for column in table_info:
    cid, name, type_, notnull, default_value, pk = column
    print(f"  Column: {name}, Type: {type_}, Not Null: {bool(notnull)}, Primary Key: {bool(pk)}")

# Close the connection
conn.close()

print("\nDatabase verification completed!")