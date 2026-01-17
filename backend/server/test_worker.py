#!/usr/bin/env python3
"""
Test script for the tex_to_pdf worker functionality.
"""

import sys
from pathlib import Path

# Add the server directory to the path so we can import the worker
sys.path.insert(0, str(Path(__file__).parent / "server"))

from workers.tex_to_pdf import process_tex_to_pdf
from db.database import create_session

def test_worker_import():
    """Test that the worker can be imported and used."""
    print("Testing worker import and functionality...")
    
    # Create a dummy session for testing
    # Note: We won't actually run pdflatex here since we don't have a real .tex file
    # This test just verifies that imports work correctly
    try:
        # Try to call the function with a fake session ID to see if imports work
        # This will fail because the session doesn't exist, but it should not fail due to import issues
        result = process_tex_to_pdf("fake-session-id")
        print(f"Function executed without import errors (expected failure due to missing session): {result}")
        
        print("Import test successful!")
        
    except ImportError as e:
        print(f"Import error occurred: {e}")
        return False
    except Exception as e:
        # If it's not an import error, that's fine for this test
        if "ModuleNotFoundError" in str(type(e)) or "ImportError" in str(type(e).__name__):
            print(f"Import-related error occurred: {e}")
            return False
        else:
            print(f"Non-import error occurred (expected): {e}")
            print("Import test successful - functions can be imported!")
    
    return True

if __name__ == "__main__":
    success = test_worker_import()
    if success:
        print("Worker import test passed!")
    else:
        print("Worker import test failed!")
        sys.exit(1)