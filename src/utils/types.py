from dataclasses import dataclass
import numpy as np


@dataclass
class AudioData:
    """ Audio Data Type for 16-bit PCM WAV """

    samples: np.ndarray  # PCM samples, dtype=int16, shape=mono:(n,1) or stereo:(n,2)
    sample_rate: int  # in Hz
