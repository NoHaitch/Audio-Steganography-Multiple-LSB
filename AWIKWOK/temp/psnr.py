import numpy as np
import math

def calculate_psnr(original_samples: np.ndarray, modified_samples: np.ndarray) -> float:
    """
    Calculates the Peak Signal-to-Noise Ratio (PSNR).
    Formula: PSNR = 10 * log10(P1^2 / (P1 - P0)^2)
    """
    original = original_samples.astype(np.float64)
    modified = modified_samples.astype(np.float64)

    p0 = np.mean(np.square(original))
    p1 = np.mean(np.square(modified))
    power_difference = p1 - p0

    if power_difference == 0:
        return float("inf")

    numerator = p1**2
    denominator = power_difference**2
    ratio = numerator / denominator

    if ratio <= 0:
        return 0.0

    return 10 * math.log10(ratio)
