import numpy as np
import librosa
import math

INPUT_FILE = "../test/original.mp3"
OUTPUT_FILE = "../test/result.mp3"

SECRET_MESSAGE = "1111111111111111111111111111111111000011110000111100001111111111111111111111111111111111111100001111000011110000111111111111111111111111111111111111110000111100001111000011111111111111111111111111111111111111000011110000111100001111111111111111111111111111111111111100001111000011110000111111111111111111111111111111111111110000111100001111000011111111111111111111111111111111111111000011110000111100001111111111111111111111111111111111111100001111000011110000111111111111111111111111111111111111110000111100001111000011111111111111111111111111111111111111000011110000111100001111111111111111111111111111111111111100001111000011110000111111111111111111111111111111111111110000111100001111000011111111111111111111111111111111111111000011110000111100001111"
START_SIG = "10101010101010"
END_SIG = "10101010101010"


def read_mp3_bytes(path):
    with open(path, "rb") as f:
        return bytearray(f.read())


def write_mp3_bytes(path, data):
    with open(path, "wb") as f:
        f.write(data)


def embed_message(mp3_bytes, message_bits):
    # Skip ID3 tag if present
    if mp3_bytes[0:3] == b"ID3":
        tag_size = (mp3_bytes[6] << 21) | (mp3_bytes[7] << 14) | (mp3_bytes[8] << 7) | mp3_bytes[9]
        offset = 10 + tag_size
    else:
        offset = 0

    # Embed into the "main data" region (naive: from offset onward)
    data = mp3_bytes[offset:]
    modified = data.copy()

    for i, bit in enumerate(message_bits):
        modified[i] = (modified[i] & 0xFE) | int(bit)

    return mp3_bytes[:offset] + modified


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


if __name__ == "__main__":
    # --- Embed step ---
    mp3_bytes = read_mp3_bytes(INPUT_FILE)
    bitstream = START_SIG + SECRET_MESSAGE + END_SIG
    stego_bytes = embed_message(mp3_bytes, bitstream)
    write_mp3_bytes(OUTPUT_FILE, stego_bytes)
    print(f"Embedded {len(bitstream)} bits into {OUTPUT_FILE}")

    # --- PSNR evaluation ---
    # Decode both MP3s into PCM using librosa
    original_pcm, sr = librosa.load(INPUT_FILE, sr=None)
    modified_pcm, _ = librosa.load(OUTPUT_FILE, sr=sr)

    # Match lengths (decoders sometimes return tiny differences)
    min_len = min(len(original_pcm), len(modified_pcm))
    original_pcm = original_pcm[:min_len]
    modified_pcm = modified_pcm[:min_len]

    psnr_value = calculate_psnr(original_pcm, modified_pcm)
    print(f"PSNR between original and stego: {psnr_value:.4f} dB")
