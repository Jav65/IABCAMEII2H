import os
import subprocess
import sys
import multiprocessing
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


def tex_to_pdf_worker(job_queue: multiprocessing.Queue, result_queue: multiprocessing.Queue):
    """
    Worker function that processes jobs from the queue.

    Args:
        job_queue: Queue to get jobs from
        result_queue: Queue to put results to
    """
    print("Starting TeX to PDF worker...")

    while True:
        try:
            # Get a job from the queue (blocking call with timeout)
            session_id = job_queue.get(timeout=1)  # Wait 1 second then check if we should continue

            if session_id is None:  # Poison pill to stop the worker
                print("Received shutdown signal, stopping worker...")
                break

            # Process the job
            success = process_tex_to_pdf(session_id)

            # Put the result back in the result queue
            result_queue.put((session_id, success))

        except multiprocessing.queues.Empty:
            # Timeout occurred, continue the loop
            continue
        except KeyboardInterrupt:
            print("Worker interrupted, shutting down...")
            break
        except Exception as e:
            print(f"Error in worker: {str(e)}")
            # Still need to handle the job that caused the exception
            try:
                # Get the job that caused the exception and mark it as failed
                session_id = job_queue.get_nowait()
                result_queue.put((session_id, False))
            except:
                pass  # No job to handle, continue


def start_worker_process(job_queue: multiprocessing.Queue, result_queue: multiprocessing.Queue) -> multiprocessing.Process:
    """
    Start a worker process that handles TeX to PDF conversions.

    Args:
        job_queue: Queue to get jobs from
        result_queue: Queue to put results to

    Returns:
        multiprocessing.Process: The started worker process
    """
    worker_process = multiprocessing.Process(
        target=tex_to_pdf_worker,
        args=(job_queue, result_queue)
    )
    worker_process.start()
    return worker_process


if __name__ == "__main__":
    # Example usage of the worker with queues
    import time

    # Create queues
    job_queue = multiprocessing.Queue()
    result_queue = multiprocessing.Queue()

    # Start the worker process
    worker_process = start_worker_process(job_queue, result_queue)

    try:
        # Example: Add some jobs to the queue
        # In a real scenario, these would come from somewhere else
        session_ids = ["session1", "session2", "session3"]

        for sid in session_ids:
            job_queue.put(sid)

        # Collect results
        results_received = 0
        while results_received < len(session_ids):
            try:
                session_id, success = result_queue.get(timeout=10)  # 10 second timeout
                print(f"Result for session {session_id}: {'Success' if success else 'Failed'}")
                results_received += 1
            except:
                print("Timeout waiting for results")
                break

    finally:
        # Send poison pill to stop the worker
        job_queue.put(None)

        # Wait for the worker to finish
        worker_process.join(timeout=5)  # Wait up to 5 seconds

        if worker_process.is_alive():
            print("Worker didn't stop gracefully, terminating...")
            worker_process.terminate()
            worker_process.join()