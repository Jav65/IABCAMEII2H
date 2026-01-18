import uuid
from pathlib import Path
from typing import Union, Generator, Optional, AsyncGenerator
from io import BytesIO


class StorageManager:
    def __init__(self, storage_path: str = "storage/files"):
        """Initialize the storage manager with the given storage path."""
        self.storage_path = Path(storage_path)
        # Create the storage directory if it doesn't exist
        self.storage_path.mkdir(parents=True, exist_ok=True)
        # Create subdirectories for different types of files
        (self.storage_path / "resources").mkdir(exist_ok=True)
        (self.storage_path / "tex").mkdir(exist_ok=True)
        (self.storage_path / "json").mkdir(exist_ok=True)
        self.init_storage()

    def init_storage(self):
        """Initialize the storage system."""
        # Storage is initialized by creating the necessary directories
        # which was already done in __init__
        pass

    def _generate_id(self) -> str:
        """Generate a unique ID."""
        return str(uuid.uuid4())

    def get_resource(self, resource_id: str, extension: Optional[str] = None) -> Path:
        """Get the file path for a resource by ID and extension."""
        if extension:
            if not extension.startswith('.'):
                extension = '.' + extension
            return self.storage_path / "resources" / f"{resource_id}{extension}"
        return self.storage_path / "resources" / resource_id

    def get_tex(self, tex_id: str) -> Path:
        """Get the file path for a TeX file by ID (returns the tex directory)."""
        return self.storage_path / "tex" / f"{tex_id}.tex"

    def get_json(self, json_id: str) -> Path:
        """Get the file path for a JSON file by ID."""
        return self.storage_path / "json" / f"{json_id}.json"

    def upload_resource_from(self, source_path: str) -> str:
        """Upload a resource from a source path by moving it to the correct location."""
        resource_id = self._generate_id()
        dest_path = self.get_resource(resource_id, Path(source_path).suffix)

        # Ensure destination directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Move the file from source to destination
        source = Path(source_path)
        source.rename(dest_path)

        return resource_id

    def upload_tex_from(self, source_path: str) -> str:
        """Upload a TeX file from a source path by moving it to the correct location."""
        tex_id = self._generate_id()
        dest_path = self.get_tex(tex_id)

        # Ensure destination directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Move the file from source to destination
        source = Path(source_path)
        source.rename(dest_path)

        return tex_id

    def upload_json_from(self, source_path: str) -> str:
        """Upload a JSON file from a source path by moving it to the correct location."""
        json_id = self._generate_id()
        dest_path = self.get_json(json_id)

        # Ensure destination directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Move the file from source to destination
        source = Path(source_path)
        source.rename(dest_path)

        return json_id


# Global instance for convenience
storage_manager = StorageManager()


# Convenience functions that use the global instance
def init_storage():
    """Initialize the storage system."""
    return storage_manager.init_storage()


def get_resource(resource_id: str, extension: Optional[str] = None) -> Path:
    """Get the file path for a resource by ID and extension."""
    return storage_manager.get_resource(resource_id, extension)


def get_tex(tex_id: str) -> Path:
    """Get the file path for a TeX file by ID."""
    return storage_manager.get_tex(tex_id)


def get_json(json_id: str) -> Path:
    """Get the file path for a JSON file by ID."""
    return storage_manager.get_json(json_id)


def upload_resource_from(source_path: str) -> str:
    """Upload a resource from a source path by moving it to the correct location."""
    return storage_manager.upload_resource_from(source_path)


def upload_tex_from(source_path: str) -> str:
    """Upload a TeX file from a source path by moving it to the correct location."""
    return storage_manager.upload_tex_from(source_path)


def upload_json_from(source_path: str) -> str:
    """Upload a JSON file from a source path by moving it to the correct location."""
    return storage_manager.upload_json_from(source_path)