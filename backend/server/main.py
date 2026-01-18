import asyncio
import os
from urllib import request
import uuid
from typing import AsyncGenerator
import json
import tempfile
import zipfile
import subprocess, tempfile, json, shutil
from pathlib import Path

from dotenv import load_dotenv

from concurrent.futures import ProcessPoolExecutor
from workers.tex_to_pdf import parse_synctex, run_latex
import traceback
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .utils import file_iterator
import db
from db.database import Session
import storage

from agents.main import runner as agent_runner


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


class ChatSelectedLine(BaseModel):
    """Selected editor line sent as chat context."""
    line_number: int
    text: str


class ChatRequest(BaseModel):
    """Chatbot API contract."""
    prompt: str
    selected_line: ChatSelectedLine | None = None
    selected_lines: list[ChatSelectedLine] | None = None 


class ChatResponse(BaseModel):
    """Chatbot response payload."""
    reply: str
    selected_line: ChatSelectedLine | None = None
    selected_lines: list[ChatSelectedLine] | None = None
    latex: str | None = None


# In-memory storage for sessions and their associated queues
session_queues: dict[str, list[asyncio.Queue]] = {}


def create_session_id() -> str:
    """Generate a unique session ID"""
    return str(uuid.uuid4())


def create_queue(session_id: str) -> asyncio.Queue:
    """Get or create a queue for a session, also initializes the session state"""
    if session_id not in session_queues:
        session_queues[session_id] = []
    queue = asyncio.Queue()
    session_queues[session_id].append(queue)
    return queue


def build_chat_prompt(
    prompt: str,
    selected_line: ChatSelectedLine | None = None,
    selected_lines: list[ChatSelectedLine] | None = None
) -> str:
    """Format the chat prompt, with context from one or more lines."""
    prompt = prompt.strip()

    if selected_lines:
        joined_lines = "\n".join(
            f"Line {l.line_number}: {l.text.strip()}" for l in selected_lines
        )
        return f"{prompt}\n\nSelected lines:\n{joined_lines}"

    if selected_line:
        line_text = selected_line.text.strip("\n")
        return f"{prompt}\n\nSelected line {selected_line.line_number}:\n{line_text}"

    return prompt


def build_chat_system_prompt() -> str:
    """System prompt that enforces a structured response."""
    return (
        "You are a helpful LaTeX assistant. Respond ONLY as JSON with keys "
        '"reply" and "latex". "reply" is a concise explanation. "latex" is the '
        "full LaTeX replacement for the selected lines, or an empty string if "
        "no change is needed. Do not wrap JSON in Markdown."
    )


def parse_chat_response(raw_response: str) -> tuple[str, str | None]:
    """Parse model output into reply + latex with a safe fallback."""
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError:
        return raw_response.strip(), None

    reply = payload.get("reply")
    latex = payload.get("latex")

    reply_text = reply.strip() if isinstance(reply, str) and reply.strip() else raw_response.strip()
    latex_text = latex if isinstance(latex, str) else None
    if latex_text is not None:
        latex_text = latex_text.strip("\n")
    return reply_text, latex_text


"""
>>>>>>> integrate-agent-w-be
def extract_zip_recursive(zip_path: Path, extract_to: Path) -> list[Path]:
    
    #Recursively extract a zip file and any nested zip files.
    #Returns a list of all extracted non-zip files.

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
"""


async def process_uploaded_file(content: bytes, temp_dir: Path) -> Path:
    """
    Process an uploaded file, extracting zips recursively if needed.
    Returns a list of file paths ready for upload.
    """
    # Save the uploaded file to temp directory
    file_path = temp_dir / "file.zip"
    file_path.parent.mkdir(parents=True, exist_ok=True)

    await asyncio.to_thread(file_path.write_bytes, content)

    return file_path
    
    """
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
    """


# Process pool for running blocking agent pipeline
agent_process_pool = ProcessPoolExecutor()

async def run_agent_pipeline(session: Session, content: bytes):
    """
    Run the agent pipeline for the given session ID.
    This is a blocking call and should be run in a separate process.
    In this case, we pass it to a ProcessPoolExecutor.
    """
    try:
        # Create a temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir_str, tempfile.TemporaryDirectory() as output_dir_str:
            temp_dir = Path(temp_dir_str)
            output_dir = Path(output_dir_str)
            
            # Process uploaded files
            zip_file_path = await process_uploaded_file(content, temp_dir)

            # Run pipeline in a separate process and wait for completion
            await asyncio.get_running_loop().run_in_executor(
                agent_process_pool,
                agent_runner,
                zip_file_path,
                session.format,
                output_dir,
            )

            # After running, upload the generated TeX file
            output_tex_path = output_dir / "main.tex"
            if not output_tex_path.exists():
                raise ValueError("Agent pipeline did not produce expected output")
            tex_id = storage.upload_tex_from(str(output_tex_path))

            # TODO: add resources

        # Update session with tex_id
        db.update_session(session.id, tex_id=tex_id)

        # Notify to client that processing is complete
        await push_event_to_session(session.id, { "event": "tex_ready", "tex_id": tex_id })
    except Exception as e:
        # Notify client of error
        print(traceback.format_exc())
        await push_event_to_session(session.id, { "event": "tex_error", "message": str(e) })


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
    queue = create_queue(session_id)

    try:
        while True:
            # Wait for event from queue
            event = await queue.get()
            event_json = json.dumps(event)
            yield f"data: {event_json}\n\n"

    except Exception as e:
        # Send error event (client needs to reload)
        event_json = json.dumps({ "event": "unexpected_error", "message": str(e) })
        yield f"data: {event_json}\n\n"


@app.post("/session", response_model=Session)
async def create_session(
    name: str = Form(...),
    format: str = Form(...),
    files: list[UploadFile] = File(...)
) -> Session:
    """Create a new session with uploaded files"""
    if len(files) == 0 or len(files) > 1:
        raise HTTPException(status_code=400, detail="Exactly one ZIP file expected")

    session = db.create_session(name=name, format=format)

    # Read the file in advance
    # This is because UploadFile cannot be passed to a background task otherwise it will close
    file = files[0]
    content = await file.read()

    # Send job to agent to start processing the resource_ids
    asyncio.create_task(run_agent_pipeline(session, content))

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
    for queue in session_queues[session_id]:
        await queue.put(event)


async def end_session_stream(session_id: str) -> None:
    """
    Signal that a session's stream has ended.
    
    This should be called when no more events will be sent.
    """
    for queue in session_queues[session_id]:
        await queue.put({ "event": "end" })
    session_queues.pop(session_id, None)


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


@app.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")

    chat_prompt = build_chat_prompt(
        prompt,
        selected_line=payload.selected_line,
        selected_lines=payload.selected_lines,
    )
    
    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")

    if api_key:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)

            def send_request() -> str:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": build_chat_system_prompt(),
                        },
                        {"role": "user", "content": chat_prompt},
                    ],
                    temperature=0.2,
                    max_tokens=800,
                    response_format={"type": "json_object"},
                )
                return response.choices[0].message.content.strip()

            raw_response = await asyncio.to_thread(send_request)
            reply, latex = parse_chat_response(raw_response)
        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Chatbot request failed: {exc}\n{tb}"
            )
        # except Exception as exc:
        #     raise HTTPException(status_code=500, detail="Chatbot request failed") from exc
    else:
        context_hint = ""
        if payload.selected_line:
            context_hint = f" (line {payload.selected_line.line_number} provided)"
        reply = f"Chatbot not configured. Prompt received{context_hint}."
        latex = None

    return ChatResponse(
        reply=reply,
        latex=latex,
        selected_line=payload.selected_line,
        selected_lines=payload.selected_lines,
    )   

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
