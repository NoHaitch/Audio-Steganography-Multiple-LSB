import os
import soundfile as sf
import numpy as np
from utils.types import AudioData


class AudioIOError(Exception):
    """ Audio I/O Exceptions. """
    pass


def load_mp3(path: str) -> AudioData:
    """
    Load an MP3 file and decode it into 16-bit PCM samples.
    Returns AudioData (samples, sample_rate).
    """
    if not os.path.exists(path):
        raise AudioIOError(f"File not found: {path}")

    _, ext = os.path.splitext(path.lower())
    if ext != ".mp3":
        raise AudioIOError(f"Unsupported file type: {ext}. Only .mp3 is allowed.")

    try:
        data, samplerate = sf.read(path, dtype="int16", always_2d=True)
        return AudioData(samples=data, sample_rate=samplerate)
    except Exception:
        raise AudioIOError(f"Failed to decode MP3 file (possibly corrupted): {path}")
