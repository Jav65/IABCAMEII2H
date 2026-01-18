import subprocess
import multiprocessing
import multiprocessing.synchronize
import tempfile
from pathlib import Path
import subprocess, tempfile, re, base64, gzip, pathlib


"""
def process_tex_to_pdf(session_id: str) -> bool:
    
    # Process a TeX to PDF conversion job.

    # Args:
    #     session_id: The ID of the session containing the TeX file info

    # Returns:
    #     bool: True if the conversion was successful, False otherwise
    
    # Get the session from the database
    session_data = get_session(session_id)
    if session_data is None:
        print(f"Session with ID {session_id} not found in database")
        return False

    tex_id = session_data.tex_id

    # In this implementation, we assume the tex_id corresponds to a file path
    # In a real implementation, you might map the UUID to an actual file path
    if tex_id is None:
        print(f"No TeX file ID associated with session {session_id}")
        return False

    # Get the actual file path from the storage manager
    tex_path = get_tex(tex_id)
    if not tex_path.exists():
        print(f"TeX file does not exist: {tex_path}")
        return False

    try:
        # Create a temporary directory for processing auxiliary files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Get the tex file directory and filename
            tex_dir = tex_path.parent
            tex_filename = tex_path.name

            # Run pdflatex command in the tex file's directory using cwd
            # This keeps the original tex file in place while allowing aux files to be created in temp dir
            # Use the filename only since we're running in the tex file's directory
            cmd = [
                'pdflatex',
                '-interaction=nonstopmode',  # Continue on errors
                # '-halt-on-error',           # Stop on fatal errors
                '-synctex=1',               # Enable synctex for forward/backward search
                '-output-directory=' + str(temp_path),  # Output aux files to temp directory
                tex_filename  # Use just the filename, not the full path
            ]
            print(f"Running command: {' '.join(cmd)}")
            print(f"Working directory: {str(tex_dir)}")
            print(f"Temp directory: {str(temp_path)}")
            print(f"Tex filename: {tex_filename}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=60,  # 60 second timeout
                cwd=str(tex_dir)  # Run in the tex file's directory
            )

            print(f"Return code: {result.returncode}")
            print(f"Stdout: {result.stdout}")
            print(f"Stderr: {result.stderr}")

            if result.returncode != 0:
                print(f"LaTeX compilation failed for session {session_id}: {result.stderr}")
                # return False

            # Find the generated PDF file in the temp directory
            pdf_path = temp_path / f"{tex_path.stem}.pdf"

            if not pdf_path.exists():
                print(f"PDF file was not generated for session {session_id}")
                return False

            # Find and handle synctex file if it exists
            synctex_path = temp_path / f"{tex_path.stem}.synctex.gz"
            if synctex_path.exists():
                # for now, just move it to the current directory with a new name
                synctex_path.rename(f"{tex_path.stem}.synctex.gz")
                print(f"Synctex file generated: {tex_path.stem}.synctex.gz")

            # Upload the PDF to storage using upload_pdf_from
            pdf_id = upload_pdf_from(str(pdf_path))
            print(f"Uploaded PDF ID: {pdf_id}")

            # Update the session in the database with the new PDF ID
            update_success = update_session(session_id, pdf_id=pdf_id)

            if update_success:
                print(f"Successfully converted TeX to PDF for session {session_id}")
                return True
            else:
                print(f"Failed to update session {session_id} in database")
                return False

    except subprocess.TimeoutExpired:
        print(f"LaTeX compilation timed out for session {session_id}")
        return False
    except Exception as e:
        print(traceback.format_exc())
        print(f"Error processing TeX to PDF for session {session_id}: {str(e)}")
        return False


def tex_to_pdf_worker(job_queue: multiprocessing.Queue, result_queue: multiprocessing.Queue, stop_event: multiprocessing.synchronize.Event):
    
    # Worker function that processes jobs from the queue.

    # Args:
    #     job_queue: Queue to get jobs from
    #     result_queue: Queue to put results to
    #     stop_event: Event to signal the worker to stop
    
    print("Starting TeX to PDF worker...")

    while not stop_event.is_set():
        try:
            # Get a job from the queue (blocking call with timeout)
            session_id = job_queue.get(timeout=1)  # Wait 1 second then check if we should continue

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


def start_worker_process(job_queue: multiprocessing.Queue, result_queue: multiprocessing.Queue, stop_event: multiprocessing.synchronize.Event) -> multiprocessing.Process:
    
    # Start a worker process that handles TeX to PDF conversions.

    # Args:
    #     job_queue: Queue to get jobs from
    #     result_queue: Queue to put results to
    #     stop_event: Event to signal the worker to stop

    # Returns:
    #     multiprocessing.Process: The started worker process
    
    worker_process = multiprocessing.Process(
        target=tex_to_pdf_worker,
        args=(job_queue, result_queue, stop_event)
    )
    worker_process.start()
    return worker_process


if __name__ == "__main__":
    # Example usage of the worker with queues
    import time

    # Create queues and stop event
    job_queue = multiprocessing.Queue()
    result_queue = multiprocessing.Queue()
    stop_event = multiprocessing.Event()

    # Start the worker process
    worker_process = start_worker_process(job_queue, result_queue, stop_event)

    try:
        # Example: Add some jobs to the queue
        # In a real scenario, these would come from somewhere else
        session_ids = ["y"]

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
        # Signal the worker to stop
        stop_event.set()

        # Wait for the worker to finish
        worker_process.join(timeout=5)  # Wait up to 5 seconds

        if worker_process.is_alive():
            print("Worker didn't stop gracefully, terminating...")
            worker_process.terminate()
            worker_process.join()

"""

def run_latex(latex_source: str):
    if not isinstance(latex_source, str) or not latex_source.strip():
        raise ValueError("LaTeX source is required")
    tmpdir = pathlib.Path(tempfile.mkdtemp())
    tex_path = tmpdir / "main.tex"
    tex_path.write_text(latex_source, encoding="utf-8")

    for _ in range(2):
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "--synctex=1", tex_path.name],
            cwd=tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

    pdf_path = tmpdir / "main.pdf"
    synctex_path = tmpdir / "main.synctex.gz"

    # base64 encodings for front‑end
    pdf_b64 = base64.b64encode(pdf_path.read_bytes()).decode()
    synctex_b64 = base64.b64encode(synctex_path.read_bytes()).decode()

    return {
        "pdf": pdf_b64,
        "synctex": synctex_b64,
        "tmpdir": str(tmpdir),
        "pdf_path": str(pdf_path),
        "tex_path": str(tex_path),
    }


def parse_synctex(base64_synctex):
    text = gzip.decompress(base64.b64decode(base64_synctex)).decode("utf-8", "ignore")

    pattern = re.compile(r"[xkhg(](\d+),(\d+):(\d+),(\d+)(?::(\d+)(?:,(\d+))?(?:,(\d+))?)?")
    SCALE = 65536

    mappings = []
    for m in pattern.finditer(text):
        if m.group(0).startswith('h') or m.group(0).startswith('g') or m.group(5) is None:
            continue
        page = int(m.group(1))
        line = int(m.group(2))
        x = int(m.group(3)) / SCALE  
        y = int(m.group(4)) / SCALE
        width = int(m.group(5)) / SCALE
        height = 10

        mappings.append({
            "line": line,
            "page": page,
            "x": x,
            "y": 595 - y,
            "width": width,
            "height": height,
        })
    return mappings
