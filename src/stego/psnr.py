import numpy as np
import math
from pathlib import Path
from fileio import load_mp3_as_pcm
from utils.exceptions import StegoCompareError


def calculate_psnr(original_samples: np.ndarray, modified_samples: np.ndarray) -> float:
    """
    Calculates the Peak Signal-to-Noise Ratio (PSNR).
    Formula: PSNR = 10 * log10(P1^2 / (P1 - P0)^2)
    """
    try:
        original = original_samples.astype(np.float64)
        modified = modified_samples.astype(np.float64)

        max_abs = max(abs(original).max(), abs(modified).max())
        original /= max_abs
        modified /= max_abs
        
        mse = np.mean(np.square(original - modified))
        
        if mse == 0:
            return float("inf")
        
        max_value = 1.0
        
        psnr = 10 * math.log10(max_value**2 / mse)
        
        return psnr
        
    except Exception as e:
        raise StegoCompareError(f"Failed to calculate PSNR: {e}") from e


def compare_mp3_files(original_path: Path, modified_path: Path) -> float:
    """
    Load two MP3 files, align lengths, and calculate PSNR.
    Wraps all errors in StegoCompareError.
    """
    try:
        original_pcm, sr_orig = load_mp3_as_pcm(original_path)
        modified_pcm, sr_mod = load_mp3_as_pcm(modified_path)

        if sr_orig != sr_mod:
            raise StegoCompareError(f"Sample rates do not match: {sr_orig} vs {sr_mod}")

        # Align lengths
        min_len = min(len(original_pcm), len(modified_pcm))
        if min_len == 0:
            raise StegoCompareError("One or both MP3 files have no samples")

        original_pcm = original_pcm[:min_len]
        modified_pcm = modified_pcm[:min_len]

        return calculate_psnr(original_pcm, modified_pcm)

    except StegoCompareError:
        raise
    except Exception as e:
        raise StegoCompareError(f"Failed to compare MP3 files: {e}") from e
