import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

# Import the database functions we created
# Add the parent directory to the path so we can import from db
sys.path.append(str(Path(__file__).parent.parent))
from db.database import get_session, update_session


def process_tex_to_pdf(session_id: str) -> bool:
    """
    Process a TeX to PDF conversion job.
    
    Args:
        session_id: The ID of the session containing the TeX file info
        
    Returns:
        bool: True if the conversion was successful, False otherwise
    """
    # Get the session from the database
    session_data = get_session(session_id)
    if not session_data:
        print(f"Session with ID {session_id} not found in database")
        return False
    
    _, tex_filepath, _ = session_data  # Extract the tex filepath
    
    # Verify that the TeX file exists
    tex_path = Path(tex_filepath)
    if not tex_path.exists():
        print(f"TeX file does not exist: {tex_filepath}")
        return False
    
    try:
        # Create a temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Copy the TeX file to the temporary directory
            # LaTeX needs to run in its own directory to properly manage aux files
            tex_filename = tex_path.name
            temp_tex_path = temp_path / tex_filename
            with open(tex_path, 'r') as src, open(temp_tex_path, 'w') as dst:
                dst.write(src.read())
            
            # Change to the temporary directory and run pdflatex
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_path)
                
                # Run pdflatex command
                result = subprocess.run([
                    'pdflatex', 
                    '-interaction=nonstopmode',  # Continue on errors
                    '-halt-on-error',           # Stop on fatal errors
                    str(tex_filename)
                ], capture_output=True, text=True, timeout=60)  # 60 second timeout
                
                if result.returncode != 0:
                    print(f"LaTeX compilation failed for session {session_id}: {result.stderr}")
                    return False
                
                # Find the generated PDF file
                pdf_path = temp_path / f"{tex_path.stem}.pdf"
                
                if not pdf_path.exists():
                    print(f"PDF file was not generated for session {session_id}")
                    return False
                
                # Create output directory if it doesn't exist
                output_dir = Path("outputs")
                output_dir.mkdir(exist_ok=True)
                
                # Generate output PDF filename
                output_pdf_path = output_dir / f"{session_id}.pdf"
                
                # Move the generated PDF to the output location
                pdf_path.rename(output_pdf_path)
                
                # Update the session in the database with the new PDF filepath
                update_success = update_session(session_id, pdf_filepath=str(output_pdf_path))
                
                if update_success:
                    print(f"Successfully converted TeX to PDF for session {session_id}")
                    return True
                else:
                    print(f"Failed to update session {session_id} in database")
                    return False
                    
            finally:
                os.chdir(original_cwd)
                
    except subprocess.TimeoutExpired:
        print(f"LaTeX compilation timed out for session {session_id}")
        return False
    except Exception as e:
        print(f"Error processing TeX to PDF for session {session_id}: {str(e)}")
        return False


def queue_tex_to_pdf_job(session_id: str) -> bool:
    """
    Queue a TeX to PDF conversion job.
    
    Args:
        session_id: The ID of the session to process
        
    Returns:
        bool: True if the job was queued successfully, False otherwise
    """
    # In a real implementation, you might add this to a proper job queue
    # For now, we'll just process it synchronously
    return process_tex_to_pdf(session_id)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python tex_to_pdf.py <session_id>")
        sys.exit(1)
    
    session_id = sys.argv[1]
    success = queue_tex_to_pdf_job(session_id)
    
    if success:
        print(f"Successfully processed session {session_id}")
        sys.exit(0)
    else:
        print(f"Failed to process session {session_id}")
        sys.exit(1)