from pathlib import Path
from types.exceptions import IOWriterError


def write_mp3_bytes(path: str | Path, data: bytearray) -> None:
    """
    Write a bytearray to an MP3 file.
    """
    file_path = Path(path)
    try:
        file_path.write_bytes(data)
    except Exception as e:
        raise IOWriterError(f"Failed to write MP3 file {path}") from e
