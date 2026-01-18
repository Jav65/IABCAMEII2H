import json
import os
import requests

BASE_URL = "http://localhost:8000"
OUTPUT_DIR = "downloaded_tex"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def create_session(name: str, format: str, file_paths: list[str]) -> str:
    """
    POST /session with attached files.
    Expects JSON response containing a session_id.
    """
    data = {
        "name": name,
        "format": format,
    }
    files = []
    for path in file_paths:
        files.append(
            (
                "files",  # field name expected by FastAPI
                (os.path.basename(path), open(path, "rb")),
            )
        )

    try:
        resp = requests.post(f"{BASE_URL}/session", data=data, files=files)
        resp.raise_for_status()
        data = resp.json()
        return data["id"]
    finally:
        for _, (_, fh) in files:
            fh.close()


def listen_for_events(session_id: str):
    """
    GET /session/{id} and listen for server-sent events.
    When a tex_ready event arrives, download the .tex file.
    """
    with requests.get(
        f"{BASE_URL}/session/{session_id}/listen",
        stream=True,
        headers={"Accept": "text/event-stream"},
    ) as resp:
        resp.raise_for_status()

        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue

            # SSE data lines look like: "data: {...}"
            if line.startswith("data:"):
                payload = line.removeprefix("data:").strip()
                event = json.loads(payload)

                if event.get("event") == "tex_ready":
                    tex_id = event["tex_id"]
                    print("Received tex_ready event, downloading .tex file...")
                    download_tex(tex_id)
                elif event.get("event") == "tex_error":
                    message = event.get("message", "No message provided")
                    print(f"Error during processing: {message}")


def download_tex(tex_id: str):
    """
    GET /tex/{tex_id} as a streamed response and save to disk.
    """
    output_path = os.path.join(OUTPUT_DIR, f"{tex_id}.tex")

    with requests.get(
        f"{BASE_URL}/tex/{tex_id}",
        stream=True,
        headers={"Accept": "application/octet-stream"},
    ) as resp:
        resp.raise_for_status()

        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

    print(f"Saved {output_path}")


if __name__ == "__main__":
    files_to_upload = [
        "resources.zip",
    ]

    session_id = create_session("placeholder_name", "cheatsheet", files_to_upload)
    print(f"Session created: {session_id}")

    listen_for_events(session_id)