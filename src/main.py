import sys
import os
import hashlib
import struct
import numpy as np
import librosa
import soundfile as sf


class AudioSteganography:
    def __init__(self, bits_per_sample=2):
        """
        Initialize the steganography class.

        Args:
            bits_per_sample: Number of LSB bits to use for hiding data (1-4 recommended)
        """
        self.bits_per_sample = bits_per_sample
        self.max_value = (1 << bits_per_sample) - 1

    def _prepare_audio(self, audio_path):
        """Load and prepare audio file for steganography."""
        try:
            # Load audio file using librosa
            audio_data, sample_rate = librosa.load(audio_path, sr=None, mono=True)

            # Convert to 16-bit integers (scale from [-1, 1] to [-32768, 32767])
            audio_samples = (audio_data * 32767).astype(np.int16)

            return audio_data, audio_samples, sample_rate

        except Exception as e:
            raise ValueError(f"Error loading audio file: {str(e)}") from e

    def _read_file_to_hide(self, file_path):
        """Read the file to be hidden and prepare it for embedding."""
        try:
            with open(file_path, "rb") as f:
                file_data = f.read()

            # Get original filename
            filename = os.path.basename(file_path)
            filename_bytes = filename.encode("utf-8")

            # Create header with file info
            # Header format: [filename_length][filename][file_size][checksum][data]
            filename_len = len(filename_bytes)
            file_size = len(file_data)
            checksum = hashlib.md5(file_data).digest()

            # Pack header
            header = struct.pack("<HH16s", filename_len, file_size, checksum)
            header += filename_bytes

            # Combine header and data
            complete_data = header + file_data

            return complete_data

        except Exception as e:
            raise IOError(f"Error reading file to hide: {str(e)}") from e

    def _data_to_bits(self, data):
        """Convert byte data to bit array."""
        bits = []
        for byte in data:
            for i in range(8):
                bits.append((byte >> (7 - i)) & 1)
        return bits

    def _bits_to_data(self, bits):
        """Convert bit array back to byte data."""
        data = bytearray()
        for i in range(0, len(bits), 8):
            if i + 7 < len(bits):
                byte = 0
                for j in range(8):
                    byte |= bits[i + j] << (7 - j)
                data.append(byte)
        return bytes(data)

    def _embed_bits_in_samples(self, audio_samples, data_bits):
        """Embed data bits into audio samples using multiple LSB."""
        if len(data_bits) * self.bits_per_sample > len(audio_samples):
            raise ValueError("File too large to hide in this audio file")

        # Create a copy of audio samples
        stego_samples = audio_samples.copy()

        # Embed data bits
        for i, bit_group in enumerate(range(0, len(data_bits), self.bits_per_sample)):
            if i >= len(stego_samples):
                break

            # Clear the LSBs
            stego_samples[i] &= ~self.max_value

            # Embed bits
            bits_to_embed = 0
            for j in range(self.bits_per_sample):
                if bit_group + j < len(data_bits):
                    bits_to_embed |= data_bits[bit_group + j] << j

            stego_samples[i] |= bits_to_embed

        return stego_samples

    def _extract_bits_from_samples(self, audio_samples, num_bits):
        """Extract hidden data bits from audio samples."""
        extracted_bits = []

        samples_needed = (num_bits + self.bits_per_sample - 1) // self.bits_per_sample

        for i in range(min(samples_needed, len(audio_samples))):
            # Extract LSBs
            lsb_value = audio_samples[i] & self.max_value

            for j in range(self.bits_per_sample):
                if len(extracted_bits) < num_bits:
                    extracted_bits.append((lsb_value >> j) & 1)

        return extracted_bits

    def hide_file(self, audio_path, file_to_hide_path, output_path):
        """Hide a file inside an audio file."""
        print(f"Loading audio file: {audio_path}")
        audio_data, audio_samples, sample_rate = self._prepare_audio(audio_path)

        print(f"Reading file to hide: {file_to_hide_path}")
        file_data = self._read_file_to_hide(file_to_hide_path)

        print("Converting data to bits...")
        data_bits = self._data_to_bits(file_data)

        # Add length information at the beginning
        data_length = len(file_data)
        length_bits = self._data_to_bits(struct.pack("<I", data_length))
        complete_bits = length_bits + data_bits

        print(f"Embedding {len(complete_bits)} bits into audio...")
        stego_samples = self._embed_bits_in_samples(audio_samples, complete_bits)

        # Convert back to float format for saving
        stego_audio_float = stego_samples.astype(np.float32) / 32767.0

        print(f"Saving steganographic audio to: {output_path}")
        sf.write(output_path, stego_audio_float, sample_rate)

        print("File successfully hidden in audio!")
        print(
            f"Capacity used: {len(complete_bits)} bits out of {len(audio_samples) * self.bits_per_sample} available"
        )

    def extract_file(self, stego_audio_path, output_dir="."):
        """Extract hidden file from steganographic audio."""
        print(f"Loading steganographic audio: {stego_audio_path}")
        _, audio_samples, _ = self._prepare_audio(stego_audio_path)

        # First, extract the length information (4 bytes = 32 bits)
        print("Extracting file length information...")
        length_bits = self._extract_bits_from_samples(audio_samples, 32)
        length_data = self._bits_to_data(length_bits)

        if len(length_data) < 4:
            raise ValueError("Could not extract file length information")

        file_length = struct.unpack("<I", length_data)[0]

        if (
            file_length <= 0 or file_length > 100 * 1024 * 1024
        ):  # Sanity check: max 100MB
            raise ValueError(f"Invalid file length: {file_length}")

        print(f"Extracting hidden file ({file_length} bytes)...")

        # Extract the actual file data
        total_bits_needed = 32 + (file_length * 8)  # length + actual data
        all_bits = self._extract_bits_from_samples(audio_samples, total_bits_needed)

        # Skip the length bits and get the file data bits
        file_bits = all_bits[32:]
        file_data = self._bits_to_data(file_bits)

        # Parse header to get filename and verify data
        try:
            header_size = struct.calcsize("<HH16s")
            if len(file_data) < header_size:
                raise ValueError("Insufficient data for header")

            filename_len, original_file_size, checksum = struct.unpack(
                "<HH16s", file_data[:header_size]
            )

            if filename_len > 255 or filename_len == 0:
                raise ValueError("Invalid filename length")

            filename = file_data[header_size : header_size + filename_len].decode(
                "utf-8"
            )
            actual_data = file_data[
                header_size
                + filename_len : header_size
                + filename_len
                + original_file_size
            ]

            # Verify checksum
            if hashlib.md5(actual_data).digest() != checksum:
                print("Warning: Checksum mismatch - file may be corrupted")

            output_path = os.path.join(output_dir, filename)

            with open(output_path, "wb") as f:
                f.write(actual_data)

            print(f"File successfully extracted to: {output_path}")
            return output_path

        except Exception as e:
            # Fallback: save as raw data
            print(f"Could not parse header ({str(e)}), saving as raw data...")
            output_path = os.path.join(output_dir, "extracted_file.bin")

            with open(output_path, "wb") as f:
                f.write(file_data)

            print(f"Raw data saved to: {output_path}")
            return output_path


def print_usage():
    """Print usage information."""
    print("Usage:")
    print(
        "  Hide file:    python main.py <input_audio.mp3> <file_to_hide> <output.mp3>"
    )
    print("  Extract file: python main.py extract <stego_audio.mp3> [output_directory]")
    print("\nExamples:")
    print("  python main.py input.mp3 secret.txt output.mp3")
    print("  python main.py extract stego.mp3")
    print("  python main.py extract stego.mp3 /path/to/output/")


def main():
    """Main function to handle command line arguments."""
    if len(sys.argv) < 3:
        print_usage()
        return

    try:
        steganography = AudioSteganography(bits_per_sample=2)

        if sys.argv[1].lower() == "extract":
            # Extract mode
            if len(sys.argv) < 3:
                print("Error: Please provide the steganographic audio file")
                return

            stego_audio_path = sys.argv[2]
            output_dir = sys.argv[3] if len(sys.argv) > 3 else "."

            if not os.path.exists(stego_audio_path):
                print(f"Error: Steganographic audio file not found: {stego_audio_path}")
                return

            steganography.extract_file(stego_audio_path, output_dir)

        else:
            # Hide mode
            if len(sys.argv) < 4:
                print(
                    "Error: Please provide input audio, file to hide, and output audio paths"
                )
                print_usage()
                return

            input_audio = sys.argv[1]
            file_to_hide = sys.argv[2]
            output_audio = sys.argv[3]

            # Validate input files
            if not os.path.exists(input_audio):
                print(f"Error: Input audio file not found: {input_audio}")
                return

            if not os.path.exists(file_to_hide):
                print(f"Error: File to hide not found: {file_to_hide}")
                return

            steganography.hide_file(input_audio, file_to_hide, output_audio)

    except Exception as e:
        print(f"Error: {str(e)}")
        return


if __name__ == "__main__":
    main()
