from dataclasses import dataclass
import numpy as np


@dataclass
class AudioData:
    """
    Audio Data Type for 16-bit PCM WAV

    Attributes:
        samples (np.ndarray): PCM samples, dtype=int16, shape=mono:(n,1) or stereo:(n,2)
        sample_rate (int): Sample rate in Hz
    """

    samples: np.ndarray
    sample_rate: int


@dataclass
class MessageData:
    """
    Message file's data.

    Attributes:
        content (bytes): The raw binary content of the file.
        size_in_bytes (int): The total size of the file in bytes.
        extension (str): The original file extension (e.g., '.png', '.txt').
    """

    content: bytes
    size_in_bytes: int
    extension: str


from dataclasses import dataclass
import numpy as np


@dataclass
class AudioData:
    """
    Audio Data Type for 16-bit PCM WAV

    Attributes:
        samples (np.ndarray): PCM samples, dtype=int16, shape=mono:(n,1) or stereo:(n,2)
        sample_rate (int): Sample rate in Hz
    """

    samples: np.ndarray
    sample_rate: int
