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
        (self.storage_path / "pdf").mkdir(exist_ok=True)
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
        tex_dir = self.storage_path / "tex" / tex_id
        return tex_dir / "main.tex"

    def get_pdf_file(self, pdf_id: str) -> Path:
        """Get the file path for a PDF file by ID."""
        return self.storage_path / "pdf" / f"{pdf_id}.pdf"

    def get_tex_asset(self, tex_id: str, asset_path: str) -> Path:
        """Get the file path for a TeX asset by tex_id and asset_path."""
        return self.storage_path / "tex" / tex_id / asset_path

    def get_pdf_synctex(self, pdf_id: str) -> Path:
        """Get the file path for a synctex file associated with a PDF."""
        return self.storage_path / "pdf" / f"{pdf_id}.synctex"

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

    def upload_pdf_from(self, source_path: str) -> str:
        """Upload a PDF file from a source path by moving it to the correct location."""
        pdf_id = self._generate_id()
        dest_path = self.get_pdf_file(pdf_id)

        # Ensure destination directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Move the file from source to destination
        source = Path(source_path)
        source.rename(dest_path)

        return pdf_id

    def upload_tex_asset_from(self, source_path: str, tex_id: str, asset_path: str) -> str:
        """Upload a TeX asset from a source path by moving it to the correct location."""
        dest_path = self.get_tex_asset(tex_id, asset_path)

        # Ensure destination directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Move the file from source to destination
        source = Path(source_path)
        source.rename(dest_path)

        return str(dest_path)

    def upload_pdf_synctex_from(self, source_path: str, pdf_id: str) -> str:
        """Upload a synctex file associated with a PDF by moving it to the correct location."""
        dest_path = self.storage_path / "pdf" / f"{pdf_id}.synctex.gz"

        # Ensure destination directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Move the file from source to destination
        source = Path(source_path)
        source.rename(dest_path)

        return str(dest_path)


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


def get_pdf_file(pdf_id: str) -> Path:
    """Get the file path for a PDF file by ID."""
    return storage_manager.get_pdf_file(pdf_id)


def get_tex_asset(tex_id: str, asset_path: str) -> Path:
    """Get the file path for a TeX asset by tex_id and asset_path."""
    return storage_manager.get_tex_asset(tex_id, asset_path)

def get_pdf_synctex(pdf_id: str) -> Path:
    """Get the file path for a synctex file associated with a PDF."""
    return storage_manager.get_pdf_synctex(pdf_id)


def upload_resource_from(source_path: str) -> str:
    """Upload a resource from a source path by moving it to the correct location."""
    return storage_manager.upload_resource_from(source_path)


def upload_tex_from(source_path: str) -> str:
    """Upload a TeX file from a source path by moving it to the correct location."""
    return storage_manager.upload_tex_from(source_path)


def upload_pdf_from(source_path: str) -> str:
    """Upload a PDF file from a source path by moving it to the correct location."""
    return storage_manager.upload_pdf_from(source_path)


def upload_tex_asset_from(source_path: str, tex_id: str, asset_path: str) -> str:
    """Upload a TeX asset from a source path by moving it to the correct location."""
    return storage_manager.upload_tex_asset_from(source_path, tex_id, asset_path)


def upload_pdf_synctex_from(source_path: str, pdf_id: str) -> str:
    """Upload a synctex file associated with a PDF by moving it to the correct location."""
    return storage_manager.upload_pdf_synctex_from(source_path, pdf_id)