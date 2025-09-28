import random
import os
import math
import hashlib
import struct
from typing import Tuple, List, Dict, Union
import numpy as np
import librosa
import soundfile as sf


class AudioSteganography:
    """
    Audio steganography implementation using LSB

    Attributes:
        bits_per_sample (int): Number of LSB bits used for data embedding (1-4)
        max_value (int): Maximum value that can be stored in the LSB bits
        signatures (Dict[int, Tuple[int, int]]): Signature patterns for different bit configurations
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

        # Signature
        self.signatures: Dict[int, Tuple[int, int]] = {
            1: (0b10101010101010, 0b10101010101010),  # 1bit
            2: (0b01010101010101, 0b01010101010101),  # 2bit
            3: (0b10101010101010, 0b01010101010101),  # 3bit
            4: (0b01010101010101, 0b10101010101010),  # 4bit
        }

    def _prepare_audio(
        self, audio_path: str
    ) -> Tuple[np.ndarray, np.ndarray, Union[int, float]]:
        """
        Load and prepare audio file for steganography processing

        Args:
            audio_path: Path to the audio file

        Returns:
            Tuple:
                - audio_data: Original float32 audio time series data
                - audio_samples: Processed int16 audio samples for embedding
                - sample_rate: Sample rate of the audio file in Hz

        Raises:
            ValueError: If the audio file cannot be loaded or processed
        """
        try:
            audio_data, sample_rate = librosa.load(audio_path, sr=None, mono=True)

            # Convert to 16-bit integers
            audio_samples = (audio_data * 32767).astype(np.int16)

            return audio_data, audio_samples, sample_rate

        except Exception as e:
            raise ValueError(f"Error loading audio file: {str(e)}") from e


    def _normalize_samples(self, audio_samples: np.ndarray) -> np.ndarray:
        """
        Normalization: A_iN = (A_i + 1) * 10^6

        Args:
            audio_samples: Input audio samples (array of int)

        Returns:
            Normalized audio samples (array of int32)
        """
        samples_float = audio_samples.astype(np.float64) / 32767.0

        normalized = (samples_float + 1) * 1000000

        return normalized.astype(np.int32)


    def _denormalize_samples(self, normalized_samples: np.ndarray) -> np.ndarray:
        """
        Denormalize samples = A_i = (A_iN * 10^-6) - 1

        Args:
            normalized_samples: Normalized audio (array of int32)

        Returns:
            De-normalized audio samples (array of int16)
        """
        denormalized = (normalized_samples.astype(np.float64) / 1000000) - 1

        audio_samples = (denormalized * 32767).astype(np.int16)

        return audio_samples


    def _calculate_random_position(self, audio_length: int, message_length: int) -> int:
        """
        Calculate random starting position

        - Irand = ceil(rand * fix(Espace/2)) + 200
        - Espace = r - rb*cb/deg - 200

        Args:
            audio_length: Total number of audio samples available
            message_length: Length of the message

        Returns:
            Random starting position

        Raises:
            ValueError: If the audio file is too small than the message
        """
        bits_needed = message_length * 8
        samples_needed = bits_needed // self.bits_per_sample
        espace = audio_length - samples_needed - 200

        if espace <= 400:
            raise ValueError("Audio file too small than thee message")

        rand_val = random.random()
        irand = int(np.ceil(rand_val * (espace // 2))) + 200

        return irand


    def _read_file_to_hide(self, file_path: str) -> bytes:
        """
        Read the file to be hidden and prepare it for embedding 

        Args:
            file_path: Path to the file that will be hidden in the audio

        Returns:
            Array of Bytes

        Raises:
            IOError: If the file cannot be read or processed
        """
        try:
            with open(file_path, "rb") as f:
                file_data = f.read()

            filename = os.path.basename(file_path)
            filename_bytes = filename.encode("utf-8")

            filename_len = len(filename_bytes)
            file_size = len(file_data)
            checksum = hashlib.md5(file_data).digest()

            header = struct.pack("<HH16s", filename_len, file_size, checksum)
            header += filename_bytes

            start_sig, end_sig = self.signatures.get(self.bits_per_sample, (0, 0))
            start_bytes = struct.pack(">H", start_sig)
            end_bytes = struct.pack(">H", end_sig)

            # start_signature + header + data + end_signature
            complete_data = start_bytes + header + file_data + end_bytes

            return complete_data

        except Exception as e:
            raise IOError(f"Error reading file to hide: {str(e)}") from e


    def _data_to_bits(self, data: bytes) -> List[int]:
        """
        Convert byte data to bit array 

        Args:
            data: Input bytes to be converted to bits

        Returns:
            List of bits
        """
        bits = []
        for byte in data:
            for i in range(8):
                bits.append((byte >> (7 - i)) & 1)
        return bits


    def _bits_to_data(self, bits: List[int]) -> bytes:
        """
        Convert bit array back to byte data

        This method reconstructs byte data from individual bits, combining
        8 bits at a time to form complete bytes

        Args:
            bits: List of integers representing individual bits (0 or 1)

        Returns:
            Reconstructed data as bytes
        """
        data = bytearray()
        for i in range(0, len(bits), 8):
            if i + 7 < len(bits):
                byte = 0
                for j in range(8):
                    byte |= bits[i + j] << (7 - j)
                data.append(byte)
        return bytes(data)


    def _embed_bits_in_samples(
        self, audio_samples: np.ndarray, data_bits: List[int], start_position: int
    ) -> np.ndarray:
        """
        Embed data bits into audio samples (main LSB)

        Args:
            audio_samples: Original audio samples
            data_bits: List of bits to embed
            start_position: Starting sample position for embedding

        Returns:
            New audio sample

        Raises:
            ValueError: If the file is too large to hide in the audio file
        """
        if start_position + (len(data_bits) // self.bits_per_sample) > len(
            audio_samples
        ):
            raise ValueError("File too large to hide in this audio file")

        stego_samples = audio_samples.copy()

        normalized = self._normalize_samples(audio_samples[start_position:])

        sample_idx = 0
        for i in range(0, len(data_bits), self.bits_per_sample):
            if sample_idx >= len(normalized):
                break

            sample_value = normalized[sample_idx]
            sample_value &= ~self.max_value

            bits_to_embed = 0
            for j in range(self.bits_per_sample):
                if i + j < len(data_bits):
                    bits_to_embed |= data_bits[i + j] << j

            sample_value |= bits_to_embed
            normalized[sample_idx] = sample_value
            sample_idx += 1

        denormalized = self._denormalize_samples(normalized[:sample_idx])
        stego_samples[start_position : start_position + sample_idx] = denormalized

        return stego_samples


    def _extract_bits_from_samples(
        self, audio_samples: np.ndarray, start_position: int, num_bits: int
    ) -> List[int]:
        """
        Extract hidden data bits from audio samples

        Args:
            audio_samples: Audio samples containing hidden data
            start_position: Starting sample position for extraction
            num_bits: Number of bits to extract

        Returns:
            Extracted bits
        """
        extracted_bits = []

        normalized = self._normalize_samples(audio_samples[start_position:])

        samples_needed = (num_bits + self.bits_per_sample - 1) // self.bits_per_sample

        for i in range(min(samples_needed, len(normalized))):
            lsb_value = normalized[i] & self.max_value

            for j in range(self.bits_per_sample):
                if len(extracted_bits) < num_bits:
                    extracted_bits.append((lsb_value >> j) & 1)

        return extracted_bits


    def hide_file(
        self, audio_path: str, file_to_hide_path: str, output_path: str
    ) -> None:
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
        print(f"Load audio file: {audio_path}")
        _, audio_samples, sample_rate = self._prepare_audio(audio_path)

        print(f"Load file to hide: {file_to_hide_path}")
        file_data = self._read_file_to_hide(file_to_hide_path)

        print("Convert to bits")
        data_bits = self._data_to_bits(file_data)

        print("Random embed position")
        start_position = self._calculate_random_position(
            len(audio_samples), len(file_data)
        )
        print(f"Starting embedding at sample position: {start_position}")

        data_length = len(file_data)
        length_bits = self._data_to_bits(struct.pack("<I", data_length))
        complete_bits = length_bits + data_bits

        print(f"Embed {len(complete_bits)} bits into audio")
        stego_samples = self._embed_bits_in_samples(
            audio_samples, complete_bits, start_position
        )

        position_bits = self._data_to_bits(struct.pack("<I", start_position))
        stego_samples = self._embed_bits_in_samples(stego_samples, position_bits, 0)

        stego_audio_float = stego_samples.astype(np.float32) / 32767.0

        print(f"Save new audio to: {output_path}")
        sf.write(output_path, stego_audio_float, sample_rate)

        print("File successfully hidden")
        print(f"Embed position: {start_position}")
        print(
            f"Capacity used: {len(complete_bits)} bits out of {(len(audio_samples) - start_position - 200) * self.bits_per_sample} available"
        )

        psnr = self._calculate_psnr(audio_samples, stego_samples)
        print(f"PSNR: {psnr:.2f} dB")


    def extract_file(self, stego_audio_path: str, output_dir: str = ".") -> str:
        """
        Extract hidden file from steganographic audio

        Args:
            stego_audio_path: Path to the steganographic audio file
            output_dir: Directory where the extracted file will be saved

        Returns:
            Path to the extracted file

        Raises:
            ValueError: If extraction fails due to invalid data or corrupted file
        """
        print(f"Load steganographic audio: {stego_audio_path}")
        _, audio_samples, _ = self._prepare_audio(stego_audio_path)

        # Extract the start position (first 32 bits)
        print("Extract embedding position")
        position_bits = self._extract_bits_from_samples(audio_samples, 0, 32)
        position_data = self._bits_to_data(position_bits)

        if len(position_data) < 4:
            raise ValueError("Could not extract position information")

        start_position = struct.unpack("<I", position_data)[0]
        print(f"Found embedding at position: {start_position}")

        print("Extract file information")
        length_bits = self._extract_bits_from_samples(audio_samples, start_position, 32)
        length_data = self._bits_to_data(length_bits)

        if len(length_data) < 4:
            raise ValueError("Could not extract file length information")

        file_length = struct.unpack("<I", length_data)[0]

        if file_length <= 0 or file_length > 100 * 1024 * 1024:  # Sanity check
            raise ValueError(f"Invalid file length: {file_length}")

        print(f"Size: ({file_length} bytes)")

        total_bits_needed = 32 + (file_length * 8)
        all_bits = self._extract_bits_from_samples(
            audio_samples, start_position, total_bits_needed
        )

        file_bits = all_bits[32:]
        file_data = self._bits_to_data(file_bits)

        # start_sig, end_sig = self.signatures.get(self.bits_per_sample, (0, 0))

        try:
            # Skip signature bytes
            data_offset = 2

            header_size = struct.calcsize("<HH16s")
            if len(file_data) < data_offset + header_size:
                raise ValueError("Insufficient data for header")

            filename_len, original_file_size, checksum = struct.unpack(
                "<HH16s", file_data[data_offset : data_offset + header_size]
            )

            data_offset += header_size

            if filename_len > 255 or filename_len == 0:
                raise ValueError("Invalid filename length")

            filename = file_data[data_offset : data_offset + filename_len].decode(
                "utf-8"
            )
            data_offset += filename_len

            actual_data = file_data[data_offset : data_offset + original_file_size]

            if hashlib.md5(actual_data).digest() != checksum:
                print("Warning: Checksum mismatch - file may be corrupted")

            output_path = os.path.join(output_dir, filename)

            with open(output_path, "wb") as f:
                f.write(actual_data)

            print(f"File successfully extracted to: {output_path}")
            return output_path

        except Exception as e:
            print(f"Error parsing embedded data: {str(e)}")

            # Log
            output_path = os.path.join(output_dir, "extracted_file.bin")
            with open(output_path, "wb") as f:
                f.write(file_data)
            print(f"Raw data saved to: {output_path}")
            return output_path


    def _calculate_psnr(self, original: np.ndarray, modified: np.ndarray) -> float:
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
