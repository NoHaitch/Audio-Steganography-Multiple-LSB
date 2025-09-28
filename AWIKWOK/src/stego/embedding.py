import numpy as np
import os
import random
import math
from utils.types import AudioData


class StegoEmbbedError(Exception):
    """Custom exception for errors during the LSB encoding process."""

    pass


SIGNATURE = "1010101010101010"  # temporary signature
SIZE_BITS = 32


def _debug_save_samples_as_bits(samples: np.ndarray, file_path: str):
    """
    Saves the binary representation of audio samples to a file for debugging.
    Formats output as 8-bit chunks, with newlines every 8 bytes.
    """
    output_dir = os.path.dirname(file_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(file_path, "w") as f:
        bytes_on_line = 0
        for sample in samples:
            bits = format(np.uint16(sample), "016b")
            byte1 = bits[:8]
            byte2 = bits[8:]

            f.write(f"{byte1} {byte2} ")
            bytes_on_line += 2  #

            if bytes_on_line >= 8:
                f.write("\n")
                bytes_on_line = 0


def embed(
    cover_audio: AudioData,
    secret_data: bytes,
    n_lsb: int,
) -> AudioData:
    """
    Embeds secret data into the LSBs of audio samples at a random start point.
    The payload is constructed as: [SIGNATURE][DATA_SIZE][SECRET_DATA]

    Args:
        cover_audio (AudioData): The original audio data to use as a cover.
        secret_data (bytes): The raw bytes of the secret file to be embedded.
        n_lsb (int): The number of least significant bits to use (from 1 to 4).

    Returns:
        AudioData: A new audio data object with the secret data embedded.
    """
    if not 1 <= n_lsb <= 4:
        raise StegoembbedError("Number of LSBs (n_lsb) must be between 1 and 4.")

    # 1. --- Construct Full Payload ---
    secret_size_in_bytes = len(secret_data)

    # Convert size to a fixed 32-bit binary string.
    size_bit_string = format(secret_size_in_bytes, f"0{SIZE_BITS}b")

    # Convert secret data bytes to a bit string.
    secret_bit_string = "".join(format(byte, "08b") for byte in secret_data)

    # Final payload: signature + data size + actual data
    payload_bits = SIGNATURE + size_bit_string + secret_bit_string
    payload_size_bits = len(payload_bits)

    # 2. --- Capacity Check and Random Start Calculation ---
    flat_samples = cover_audio.samples.flatten()
    num_samples = flat_samples.size

    required_samples = math.ceil(payload_size_bits / n_lsb)

    if required_samples > num_samples:
        raise StegoembbedError(
            f"Payload is too large to hide in the cover audio.\n"
            f"Required samples: {required_samples}\n"
            f"Available samples: {num_samples}"
        )

    # Determine the latest possible start index and pick a random one.
    max_start_index = num_samples - required_samples
    start_index = random.randint(0, max_start_index)

    print(f"[*] Embedding payload at random sample index: {start_index}")

    # 3. --- LSB Embedding ---
    modified_samples = flat_samples.copy()

    # DEBUG: Save the original sample bits before modification.
    _debug_save_samples_as_bits(flat_samples, "../test/before.txt")

    mask = ~((1 << n_lsb) - 1)

    payload_bit_index = 0
    current_sample_index = start_index

    while payload_bit_index < payload_size_bits:
        bits_to_embed_str = payload_bits[
            payload_bit_index : payload_bit_index + n_lsb
        ].ljust(n_lsb, "0")
        bits_to_embed_int = int(bits_to_embed_str, 2)

        modified_samples[current_sample_index] = (
            modified_samples[current_sample_index] & mask
        ) | bits_to_embed_int

        payload_bit_index += n_lsb
        current_sample_index += 1

    # DEBUG: Save the modified sample bits after modification.
    _debug_save_samples_as_bits(modified_samples, "../test/after.txt")

    # 4. --- Reshape and Return ---
    stego_samples = modified_samples.reshape(cover_audio.samples.shape)

    return AudioData(samples=stego_samples, sample_rate=cover_audio.sample_rate)
