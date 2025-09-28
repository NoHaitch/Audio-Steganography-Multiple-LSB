from pathlib import Path
from typing import Tuple
from utils import IOReaderError
import librosa
import numpy as np


def read_mp3_bytes(path: str | Path) -> bytearray:
    """
    Read an MP3 file into a bytearray.
    Raises IOReaderError if file is not found or not valid.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise IOReaderError(f"MP3 file not found: {path}")

    try:
        data = file_path.read_bytes()
    except Exception as e:
        raise IOReaderError(f"Failed to read MP3 file {path}") from e

    if not (data.startswith(b"ID3") or data[0:2] == b"\xff\xfb"):
        raise IOReaderError(f"File {path} does not look like a valid MP3 file")

    return bytearray(data)


def skip_id3_tag(mp3_bytes: bytearray) -> Tuple[int, bytearray]:
    """
    Skip the ID3v2 tag if present.
    Returns a tuple: (offset, audio_data)
    - offset: number of bytes skipped
    - audio_data: main MP3 audio data
    """
    if mp3_bytes[0:3] == b"ID3":
        tag_size = (
            (mp3_bytes[6] & 0x7F) << 21
            | (mp3_bytes[7] & 0x7F) << 14
            | (mp3_bytes[8] & 0x7F) << 7
            | (mp3_bytes[9] & 0x7F)
        )
        offset = 10 + tag_size
        return offset, mp3_bytes[offset:]
    return 0, mp3_bytes


def load_mp3_as_pcm(path: str | Path) -> Tuple[np.ndarray, int]:
    """
    Load an MP3 file as PCM samples using librosa.
    Returns (samples, sample_rate).
    """
    file_path = Path(path)
    if not file_path.exists():
        raise IOReaderError(f"MP3 file not found: {path}")

    try:
        samples, sr = librosa.load(file_path, sr=None)
        return samples, sr
    except Exception as e:
        raise IOReaderError(f"Failed to decode MP3 file {path}") from e
