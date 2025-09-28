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


def save_mp3(path: str, audio_data: AudioData) -> None:
    """
    Save 16-bit PCM samples to MP3 file.
    """
    _, ext = os.path.splitext(path.lower())
    if ext != ".mp3":
        raise AudioIOError(f"Invalid output format: {ext}. Only .mp3 is supported.")

    try:
        sf.write(path, audio_data.samples, audio_data.sample_rate, format="MP3")
    except Exception as e:
        error_message = (
            f"Failed to save MP3 file to {path}. "
            "This may be because your system's 'libsndfile' installation "
            "does not support writing MP3 files. Please ensure it was "
            f"compiled with the LAME encoder library. Original error: {e}"
        )
        raise AudioIOError(error_message) from e
