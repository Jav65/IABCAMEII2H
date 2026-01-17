import asyncio
from urllib import request
import uuid
from typing import AsyncGenerator
import json
import tempfile
import zipfile
import subprocess, tempfile, json, shutil
from pathlib import Path
from workers.tex_to_pdf import parse_synctex, run_latex
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .utils import file_iterator
import db
from db.database import Session
import storage


# Initialize FastAPI app
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],         # or list of specific origins
    allow_credentials=True,
    allow_methods=["*"],         # allows OPTIONS, GET, POST, etc.
    allow_headers=["*"],
)

class SessionCreate(BaseModel):
    """Request body for creating a new session"""
    name: str | None = None


# In-memory storage for sessions and their associated queues
session_queues: dict[str, asyncio.Queue] = {}


def create_session_id() -> str:
    """Generate a unique session ID"""
    return str(uuid.uuid4())


def get_or_create_queue(session_id: str) -> asyncio.Queue:
    """Get or create a queue for a session, also initializes the session state"""
    if session_id not in session_queues:
        session_queues[session_id] = asyncio.Queue()
    return session_queues[session_id]


def extract_zip_recursive(zip_path: Path, extract_to: Path) -> list[Path]:
    """
    Recursively extract a zip file and any nested zip files.
    Returns a list of all extracted non-zip files.
    """
    extracted_files = []
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
    
    # Process all extracted files
    for item in extract_to.rglob('*'):
        if item.is_file():
            if item.suffix.lower() == '.zip':
                # Recursively extract nested zip
                nested_extract_dir = item.parent / item.stem
                nested_extract_dir.mkdir(exist_ok=True)
                nested_files = extract_zip_recursive(item, nested_extract_dir)
                extracted_files.extend(nested_files)
                # Remove the zip file after extraction
                item.unlink()
            else:
                extracted_files.append(item)
    
    return extracted_files


async def process_uploaded_file(file: UploadFile, temp_dir: Path) -> list[Path]:
    """
    Process an uploaded file, extracting zips recursively if needed.
    Returns a list of file paths ready for upload.
    """
    # Save the uploaded file to temp directory
    file_path = temp_dir / file.filename
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    content = await file.read()
    await asyncio.to_thread(file_path.write_bytes, content)
    
    # Check if it's a zip file
    if file.filename.lower().endswith('.zip'):
        # Extract recursively in a thread
        extract_dir = temp_dir / f"{file.filename}_extracted"
        extract_dir.mkdir(exist_ok=True)
        
        extracted_files = await asyncio.to_thread(
            extract_zip_recursive, 
            file_path, 
            extract_dir
        )
        
        # Remove the original zip
        await asyncio.to_thread(file_path.unlink)
        return extracted_files
    else:
        return [file_path]


async def event_stream(session_id: str) -> AsyncGenerator[str, None]:
    """
    Generator that yields server-side events from a session's queue.

    Once calling this, the server should send a sync event to let the client know
    of the current state of the session.

    Another coroutine can push events to the queue via:
        queue = session_queues[session_id]
        await queue.put(event_data)
    
    Send a None value to signal end of stream.
    """
    queue = get_or_create_queue(session_id)

    try:
        while True:
            # Wait for event from queue
            event = await queue.get()
            event_json = json.dumps(event)
            yield f"data: {event_json}\n\n"

    except Exception as e:
        # Send error event (client needs to reload)
        yield "data: {\"event\": \"error\"}\n\n"


@app.post("/session", response_model=Session)
async def create_session(
    name: str,
    format: str,
    files: list[UploadFile] = File(...)
) -> Session:
    """Create a new session with uploaded files"""
    
    # Create a temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        
        # Process all uploaded files
        all_files = []
        for file in files:
            processed_files = await process_uploaded_file(file, temp_dir)
            all_files.extend(processed_files)
        
        # Upload each file as a resource
        resource_ids = []
        for file_path in all_files:
            # Upload to storage
            resource_id = storage.upload_resource_from(str(file_path))
            resource_ids.append(resource_id)
    
    # Create session in database
    session = db.create_session(name=name, format=format)
    
    # Initialize queue for this session
    get_or_create_queue(session.id)
    
    # TODO: Send job to agent to start processing the resource_ids

    return session


@app.get("/session/{session_id}", response_model=Session)
async def get_session(session_id: str) -> Session:
    """Get session details by ID"""
    session = db.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.get("/tex/{tex_id}")
async def get_tex(tex_id: str) -> dict:
    """Get TeX data by ID"""
    tex_filepath = storage.get_tex(tex_id)
    if not tex_filepath.exists():
        raise HTTPException(status_code=404, detail="TeX not found")

    return StreamingResponse(
        file_iterator(tex_filepath),
        media_type="application/x-tex",
        headers={
            "Content-Disposition": f'inline; filename="{tex_filepath.name}"',
            "Content-Length": str(tex_filepath.stat().st_size),
        },
    )


@app.get("/pdf/{pdf_id}")
async def get_pdf(pdf_id: str) -> dict:
    """Get PDF data by ID"""
    pdf_filepath = storage.get_pdf(pdf_id)
    if not pdf_filepath.exists():
        raise HTTPException(status_code=404, detail="PDF not found")

    return StreamingResponse(
        file_iterator(pdf_filepath),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{pdf_filepath.name}"',
            "Content-Length": str(pdf_filepath.stat().st_size),
        },
    )


@app.get("/synctex/{pdf_id}")
async def get_synctex(pdf_id: str) -> dict:
    """Get Synctex data by PDF ID"""
    synctex_filepath = storage.get_pdf_synctex(pdf_id)
    if not synctex_filepath.exists():
        raise HTTPException(status_code=404, detail="Synctex not found")

    return StreamingResponse(
        file_iterator(synctex_filepath),
        media_type="application/x-synctex",
        headers={
            "Content-Disposition": f'inline; filename="{synctex_filepath.name}"',
            "Content-Length": str(synctex_filepath.stat().st_size),
        },
    )


@app.get("/session/{session_id}/listen")
async def listen_session(session_id: str):
    """
    Server-Sent Events endpoint.
    
    Client can connect and listen for events. Another coroutine can
    push data via: await session_queues[session_id].put(event)
    
    Send None to signal end of stream.
    """
    if db.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return StreamingResponse(
        event_stream(session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


async def push_event_to_session(session_id: str, event: dict) -> None:
    """
    Push an event to a session's stream.
    
    This is meant to be called by other coroutines that generate chunks.
    
    Args:
        session_id: The session ID to push to
        event: The event data (dict)
    """
    if session_id not in session_queues:
        get_or_create_queue(session_id)
    
    queue = session_queues[session_id]
    await queue.put(event)


async def end_session_stream(session_id: str) -> None:
    """
    Signal that a session's stream has ended.
    
    This should be called when no more events will be sent.
    """
    if session_id in session_queues:
        queue = session_queues[session_id]
        await queue.put({ "event": "end" })
        
@app.post("/compile")
async def compile_live(request: Request):
    payload = await request.json()
    source = payload.get("source")
    if not isinstance(source, str) or not source.strip():
        return JSONResponse({"error": "Missing LaTeX source"}, status_code=400)

    try:
        result = run_latex(source)
    except subprocess.CalledProcessError as exc:
        output = (
            exc.stdout.decode("utf-8", "ignore")
            if isinstance(exc.stdout, (bytes, bytearray))
            else str(exc.stdout)
        )
        return JSONResponse(
            {"error": "LaTeX compilation failed", "details": output},
            status_code=400,
        )
    except Exception as exc:
        return JSONResponse(
            {"error": "Server error", "details": str(exc)},
            status_code=500,
        )

    mappings = parse_synctex(result["synctex"])
    shutil.rmtree(result["tmpdir"], ignore_errors=True)

    return JSONResponse(
        {
            "source": source,
            "pdf": result["pdf"],
            "synctex": result["synctex"],
            "mappings": mappings,
        }
    )

if __name__ == "__main__":
    # This is typically not used when running with uvicorn
    # uvicorn main:app --reload
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
