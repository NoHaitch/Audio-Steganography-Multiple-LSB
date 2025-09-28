import os
import math
from typing import Tuple, Dict
import numpy as np
import librosa


class AudioSteganography:
    """
    Audio steganography implementation using LSB

    Attributes:
        bits_per_sample (int): Number of LSB bits used for data embedding (1-4)
        max_value (int): Maximum value that can be stored in the LSB bits
        signatures (Dict[int, Tuple[str, str]]): Signature patterns for different bit configurations as bit strings
    """

    def __init__(self, bits_per_sample: int = 2) -> None:
        """
        Initialize the audio steganography object

        Args:
            bits_per_sample: Number of LSB bits to use for hiding data (1-4 recommended)

        Raises:
            ValueError: If bits_per_sample is not in the valid range [1-4]
        """
        if not 1 <= bits_per_sample <= 4:
            raise ValueError("bits_per_sample must be between 1 and 4")

        self.bits_per_sample = bits_per_sample
        self.max_value = (1 << bits_per_sample) - 1

        # Signature patterns as bit strings (like in embed.py)
        self.signatures: Dict[int, Tuple[str, str]] = {
            1: ("10101010101010", "10101010101010"),  # 1bit
            2: ("01010101010101", "01010101010101"),  # 2bit
            3: ("10101010101010", "01010101010101"),  # 3bit
            4: ("01010101010101", "10101010101010"),  # 4bit
        }


    def read_file_bytes(self, path: str) -> bytearray:
        """
        Open file as bytestream

        Args:
            path (str): path to the file

        Returns:
            bytearray: bytestream repr of file
        """
        with open(path, "rb") as f:
            return bytearray(f.read())


    def write_file_bytes(self, path: str, data: bytearray):
        """
        Write bytestream to the file back

        Args:
            path (str): path to the output file
            data (bytearray): data to be written
        """
        with open(path, "wb") as f:
            f.write(data)


    def embed_message(self, mp3_bytes: bytearray, message_bits: str) -> bytearray:
        """
        Embedding message into the MP3 file

        Args:
            mp3_bytes (bytearray): data of the audio file
            message_bits (str): message bits as string to be embedded

        Returns:
            bytearray: new bytestream audio contains embedded message
        """
        # Skip ID3 tag if present
        if mp3_bytes[0:3] == b"ID3":
            tag_size = (
                (mp3_bytes[6] << 21)
                | (mp3_bytes[7] << 14)
                | (mp3_bytes[8] << 7)
                | mp3_bytes[9]
            )
            offset = 10 + tag_size
        else:
            offset = 0

        # Embed into the "main data" region (naive: from offset onward)
        data = mp3_bytes[offset:]
        modified = data.copy()

        for i, bit in enumerate(message_bits):
            if i >= len(modified):
                break
            modified[i] = (modified[i] & 0xFE) | int(bit)

        return mp3_bytes[:offset] + modified


    def calculate_psnr(self, original: np.ndarray, modified: np.ndarray) -> float:
        """
        Calculate PSNR (Peak Signal-to-Noise Ratio) between original and modified audio

        Args:
            original: Original audio samples
            modified: Modified (steganographic) audio samples

        Returns:
            PSNR value in decibels (dB)
        """
        original = original.astype(np.float64)
        modified = modified.astype(np.float64)

        # p0 = signal power of original audio
        # p1 = signal power of modified audio
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

        psnr = 10 * math.log10(ratio)

        return psnr


    def embed(self, audio_path: str, file_to_hide_path: str, output_path: str) -> None:
        """
        Hide a file inside an audio file. Main function to be called

        Args:
            audio_path: Cover audio file path
            file_to_hide_path: Path to the file that will be hidden
            output_path: Path where the steganographic audio will be saved

        Raises:
            ValueError: If audio file is too small or files cannot be processed
            IOError: If files cannot be read or written
        """
        mp3_bytes = self.read_file_bytes(audio_path)
        message_data = self.read_file_bytes(file_to_hide_path)

        # Extract file extension (e.g., ".jpg")
        ext = os.path.splitext(file_to_hide_path)[1].lstrip(".") or "bin"
        ext_bytes = ext.encode("utf-8")

        if len(ext_bytes) > 255:
            raise ValueError("File extension too long!")

        # Build header: 1 byte length + extension string
        header = bytes([len(ext_bytes)]) + ext_bytes

        # Convert header + data into bit string
        header_bits = "".join(format(b, "08b") for b in header)
        message_bits = "".join(format(b, "08b") for b in message_data)

        # Wrap with signatures
        start_sig, end_sig = self.signatures[self.bits_per_sample]
        bitstream = start_sig + header_bits + message_bits + end_sig

        # Embed
        stego_bytes = self.embed_message(mp3_bytes, bitstream)
        self.write_file_bytes(output_path, stego_bytes)
        print(f"Embedded {len(message_data)} bytes ({ext}) into {output_path}")


    def extract(self, stego_audio_path: str, output_path: str):
        """
        Extract hidden file from a stego MP3 using the START and END signatures.

        Args:
            stego_audio_path (str): Path to stego audio file
            output_path (str): Path where the extracted file will be saved
        """
        stego_bytes = self.read_file_bytes(stego_audio_path)

        # Skip ID3 tag if present
        if stego_bytes[0:3] == b"ID3":
            tag_size = (
                (stego_bytes[6] << 21)
                | (stego_bytes[7] << 14)
                | (stego_bytes[8] << 7)
                | stego_bytes[9]
            )
            offset = 10 + tag_size
        else:
            offset = 0

        data = stego_bytes[offset:]

        # Extract LSBs into bitstream
        bitstream = "".join(str(b & 1) for b in data)

        # Find signatures
        start_sig, end_sig = self.signatures[self.bits_per_sample]
        start_index = bitstream.find(start_sig)
        end_index = bitstream.find(end_sig, start_index + len(start_sig))

        if start_index == -1 or end_index == -1:
            raise ValueError("Signatures not found in the stego file!")

        # Extract payload bits between signatures
        payload_bits = bitstream[start_index + len(start_sig):end_index]

        # Convert to bytes
        payload_bytes = bytearray(
            int(payload_bits[i:i+8], 2) for i in range(0, len(payload_bits), 8)
        )

        # Parse header
        ext_len = payload_bytes[0]
        ext = payload_bytes[1:1+ext_len].decode("utf-8")
        hidden_data = payload_bytes[1+ext_len:]

        # Build output path with extension
        final_output = f"{output_path}.{ext}"
        self.write_file_bytes(final_output, hidden_data)
        print(f"Extracted hidden file ({ext}, {len(hidden_data)} bytes) → {final_output}")


if __name__ == "__main__":
    opt = int(input("1: hide, 2: extract"))
    audio = AudioSteganography(2)
    if opt == 1:
        # --- Embed step ---
        audio.embed(os.path.abspath("original.mp3"), os.path.abspath("foto1.jpg"), os.path.abspath("out2.mp3"))

        original_pcm, sr = librosa.load(os.path.abspath("original.mp3"), sr=None)
        modified_pcm, _ = librosa.load(os.path.abspath("out2.mp3"), sr=sr)

        # Match lengths (decoders sometimes return tiny differences)
        min_len = min(len(original_pcm), len(modified_pcm))
        original_pcm = original_pcm[:min_len]
        modified_pcm = modified_pcm[:min_len]

        psnr_value = audio.calculate_psnr(original_pcm, modified_pcm)
        print(f"PSNR between original and stego: {psnr_value:.4f} dB")
    else:
        audio.extract(os.path.abspath("out2.mp3"), "")
