import os
import platform
import subprocess


class AudioPlayerError(Exception):
    """ Audio Player Exceptions """
    pass


def play_audio(file_path: str) -> None:
    """ Open audio file using system default. Only allow MP3 and WAV. """
    if not os.path.exists(file_path):
        raise AudioPlayerError(f"Audio file not found: {file_path}")

    _, ext = os.path.splitext(file_path.lower())

    if ext == ".wav":  # Validate WAV
        if not _is_wav(file_path):
            raise AudioPlayerError("File extension is .wav but header is invalid.")
    elif ext == ".mp3":  # Validate MP3
        if not _is_mp3(file_path):
            raise AudioPlayerError("File extension is .mp3 but header is invalid.")
    else:
        raise AudioPlayerError(
            f"Unsupported file type: {ext}. Only MP3 and WAV are allowed."
        )

    system = platform.system()

    # system call - open file
    try:
        if system == "Windows":
            os.startfile(file_path)
        elif system == "Darwin":  # mac
            subprocess.run(["open", file_path], check=False)
        else:  # Linux
            subprocess.run(["xdg-open", file_path], check=False)
    except Exception as e:
        raise AudioPlayerError(f"Failed to open audio file: {e}") from e


def _is_wav(file_path: str) -> bool:
    """" Check file header for WAV """
    with open(file_path, "rb") as f:
        header = f.read(12)
    return header.startswith(b"RIFF") and header[8:12] == b"WAVE"


def _is_mp3(file_path: str) -> bool:
    """" Check file header for MP3 """
    with open(file_path, "rb") as f:
        header = f.read(3)
    return (
        header.startswith(b"ID3")
        or header[:2] == b"\xff\xfb"
        or header[:2] == b"\xff\xf3"
        or header[:2] == b"\xff\xf2"
    )
