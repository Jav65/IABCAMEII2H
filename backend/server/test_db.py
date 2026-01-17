#!/usr/bin/env python3
"""
Test script for the database functionality.
"""

import os
import sys
from pathlib import Path

# Add the server directory to the path so we can import the db module
sys.path.insert(0, str(Path(__file__).parent))

from db.database import (
    create_session,
    get_session,
    update_session,
    delete_session,
    list_sessions,
    DatabaseManager
)


def test_database():
    """Test the database functionality."""
    print("Testing database functionality...")
    
    # Create a sample session
    tex_path = "uploads/sample.tex"
    pdf_path = "outputs/sample.pdf"
    
    session_id = create_session(tex_path, pdf_path)
    print(f"Created session with ID: {session_id}")
    
    # Retrieve the session
    session = get_session(session_id)
    if session:
        sid, tex_fp, pdf_fp = session
        print(f"Retrieved session: ID={sid}, TeX={tex_fp}, PDF={pdf_fp}")
    
    # List all sessions
    all_sessions = list_sessions()
    print(f"All sessions: {len(all_sessions)}")
    for s in all_sessions:
        print(f"  - ID: {s[0]}, TeX: {s[1]}, PDF: {s[2]}")
    
    # Update the session
    new_tex_path = "uploads/updated_sample.tex"
    success = update_session(session_id, tex_filepath=new_tex_path)
    print(f"Updated session: {success}")
    
    # Check the updated session
    updated_session = get_session(session_id)
    if updated_session:
        sid, tex_fp, pdf_fp = updated_session
        print(f"Updated session: ID={sid}, TeX={tex_fp}, PDF={pdf_fp}")
    
    # Clean up - delete the session
    delete_success = delete_session(session_id)
    print(f"Deleted session: {delete_success}")
    
    # Verify deletion
    remaining_sessions = list_sessions()
    print(f"Sessions after deletion: {len(remaining_sessions)}")
    
    print("Database test completed!")


if __name__ == "__main__":
    test_database()