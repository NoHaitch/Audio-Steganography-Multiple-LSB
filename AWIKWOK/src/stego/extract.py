import numpy as np
import random
import math
import os  # <-- Added import
from utils.types import AudioData
from stego.embedding import SIGNATURES, SIZE_BITS


class StegoExtractError(Exception):
    """Custom exception for errors during the LSB extraction process."""
    pass


# Helper function for debugging, similar to the one in embedding.py
def _debug_save_samples_as_bits(samples: np.ndarray, file_path: str, start: int, length: int):
    """
    Saves the binary representation of audio samples to a file for debugging.
    """
    output_dir = os.path.dirname(file_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(file_path, "w") as f:
        byte_count = 0
        line_bytes = []
        # Loop through the specified range of samples
        for i in range(start, start + length):
            # Ensure we don't read past the end of the array
            if i >= len(samples):
                break
            # Format the 16-bit sample into a binary string
            bits = format(np.uint16(samples[i]), "016b")
            # Split into two 8-bit strings (bytes)
            byte1 = bits[:8]
            byte2 = bits[8:]
            line_bytes.extend([byte1, byte2])
            byte_count += 2
            # Write a new line every 4 bytes for readability
            if byte_count % 4 == 0:
                f.write(" ".join(line_bytes) + "\n")
                line_bytes = []
        # Write any remaining bytes that didn't form a full line
        if line_bytes:
            f.write(" ".join(line_bytes) + "\n")


def extract(
    stego_audio: AudioData,
    n_lsb: int,
    seed: int = None,
) -> bytes:
    """
    Extracts the secret data from the stego audio using the provided seed and n_lsb.
    Args:
        stego_audio (AudioData): The audio data containing the embedded secret.
        n_lsb (int): The number of least significant bits used for embedding (1-4).
        seed (int, optional): The seed used for random start location.
    Returns:
        bytes: The extracted secret data.
    """
    if not 1 <= n_lsb <= 4:
        raise StegoExtractError("Number of LSBs (n_lsb) must be between 1 and 4.")
    if n_lsb not in SIGNATURES:
        raise StegoExtractError(f"No signature defined for n_lsb={n_lsb}")

    start_signature, end_signature = SIGNATURES[n_lsb]
    flat_samples = stego_audio.samples.flatten()
    num_samples = flat_samples.size

    # Calculate bit lengths
    start_sig_len = len(start_signature)
    end_sig_len = len(end_signature)
    size_len = SIZE_BITS

    # First, extract enough bits for start signature and size
    min_payload_bits = start_sig_len + size_len
    required_samples = math.ceil(min_payload_bits / n_lsb)
    max_start_index = num_samples - required_samples

    if seed is not None:
        random.seed(seed)
    start_index = random.randint(0, max_start_index)

    # [DEBUG] Save the stego object samples from the calculated start index
    debug_file_path = "../test/stego-object.txt"
    # Max 500 bytes = 250 samples (since each sample is 16 bits / 2 bytes)
    debug_length = min(250, num_samples - start_index)
    print(f"[*] Saving debug samples to '{debug_file_path}' (start_index={start_index}, num_samples={debug_length})")
    _debug_save_samples_as_bits(flat_samples, debug_file_path, start_index, debug_length)

    # Extract bits for start signature and size
    bits = []
    for i in range(start_index, start_index + required_samples):
        sample = flat_samples[i]
        bits.extend([int(b) for b in format(sample & ((1 << n_lsb) - 1), f"0{n_lsb}b")])

    # Get the start signature and size bits
    sig_bits = "".join(str(b) for b in bits[:start_sig_len])
    size_bits = "".join(str(b) for b in bits[start_sig_len : start_sig_len + SIZE_BITS])

    if sig_bits != start_signature:
        print(f"[DEBUG] Extracted start signature: {sig_bits}")
        print(f"[DEBUG] Expected start signature: {start_signature}")
        raise StegoExtractError("Start signature mismatch. Wrong n_lsb or seed?")

    secret_size = int(size_bits, 2)

    # Now extract the secret data bits and end signature
    total_payload_bits = start_sig_len + size_len + secret_size * 8 + end_sig_len
    total_required_samples = math.ceil(total_payload_bits / n_lsb)

    secret_bits = []
    # Ensure not to read past the end of the file
    end_read_index = min(start_index + total_required_samples, num_samples)
    for i in range(start_index, end_read_index):
        sample = flat_samples[i]
        secret_bits.extend(
            [int(b) for b in format(sample & ((1 << n_lsb) - 1), f"0{n_lsb}b")]
        )

    # Only take the secret data bits
    secret_data_bits = secret_bits[
        start_sig_len + size_len : start_sig_len + size_len + secret_size * 8
    ]

    # Check end signature
    end_sig_start = start_sig_len + size_len + secret_size * 8
    end_sig_end = end_sig_start + end_sig_len
    end_sig_bits = "".join(str(b) for b in secret_bits[end_sig_start:end_sig_end])

    if end_sig_bits != end_signature:
        print(f"[DEBUG] Extracted end signature: {end_sig_bits}")
        print(f"[DEBUG] Expected end signature: {end_signature}")
        raise StegoExtractError(
            "End signature mismatch. Data may be corrupted or wrong parameters."
        )

    # Convert bits to bytes
    secret_bytes = bytearray()
    for i in range(0, len(secret_data_bits), 8):
        byte_chunks = secret_data_bits[i:i+8]
        if len(byte_chunks) == 8:
            byte_str = "".join(map(str, byte_chunks))
            secret_bytes.append(int(byte_str, 2))

    return bytes(secret_bytes)