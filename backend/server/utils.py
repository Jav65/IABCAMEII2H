from pathlib import Path

FILE_CHUNK_SIZE = 8192  # 8 KB

def file_iterator(path: Path, chunk_size: int = FILE_CHUNK_SIZE):
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            yield chunk