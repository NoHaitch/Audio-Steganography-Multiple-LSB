import random
import os
import math
import hashlib
import struct
from typing import Tuple, List, Dict, Union, Optional
import numpy as np


class AudioSteganography:
    """
    MP3 steganography that works directly on compressed MP3 frame data.
    This embeds data into the audio data portion of MP3 frames after compression.
    """

    def __init__(self, bits_per_sample: int = 1) -> None:
        """
        Initialize MP3 frame-based steganography
        
        Args:
            bits_per_sample: Number of LSB bits to use per byte (1-4)
        """
        if not 1 <= bits_per_sample <= 4:
            raise ValueError("bits_per_sample must be between 1 and 4")
        
        self.bits_per_sample = bits_per_sample
        self.max_value = (1 << bits_per_sample) - 1
        
        # MP3 frame sync pattern
        self.SYNC_WORD = 0xFFF
        
        # Signature patterns from the paper
        self.signatures: Dict[int, Tuple[int, int]] = {
            1: (0b10101010101010, 0b10101010101010),
            2: (0b01010101010101, 0b01010101010101),
            3: (0b10101010101010, 0b01010101010101),
            4: (0b01010101010101, 0b10101010101010),
        }

    def _find_mp3_frames(self, mp3_data: bytes) -> List[Tuple[int, int, Dict]]:
        """
        Find all MP3 frames in the compressed data
        
        Returns:
            List of tuples (start_pos, frame_size, header_info)
        """
        frames = []
        i = 0
        
        while i < len(mp3_data) - 4:
            # Look for sync word (11 bits set to 1)
            if i < len(mp3_data) - 1:
                sync = ((mp3_data[i] << 3) | (mp3_data[i + 1] >> 5)) & 0x7FF
                
                if sync == 0x7FF:  # Found potential frame header
                    header = struct.unpack('>I', mp3_data[i:i+4])[0]
                    
                    # Parse header to get frame info
                    header_info = self._parse_mp3_header(header)
                    
                    if header_info and header_info['frame_size'] > 0:
                        # Verify this is a valid frame
                        frame_size = header_info['frame_size']
                        
                        # Check if we can find the next sync word where expected
                        next_pos = i + frame_size
                        if next_pos < len(mp3_data) - 1:
                            next_sync = ((mp3_data[next_pos] << 3) | 
                                       (mp3_data[next_pos + 1] >> 5)) & 0x7FF
                            
                            if next_sync == 0x7FF or next_pos >= len(mp3_data) - 4:
                                # Valid frame found
                                frames.append((i, frame_size, header_info))
                                i = next_pos
                                continue
                
            i += 1
        
        return frames

    def _parse_mp3_header(self, header: int) -> Optional[Dict]:
        """
        Parse MP3 frame header (based on paper's Table 1)
        """
        # Extract header fields
        sync = (header >> 21) & 0x7FF
        if sync != 0x7FF:
            return None
        
        version = (header >> 19) & 0x3
        layer = (header >> 17) & 0x3
        protection = (header >> 16) & 0x1
        bitrate_idx = (header >> 12) & 0xF
        sampling_idx = (header >> 10) & 0x3
        padding = (header >> 9) & 0x1
        
        # Validate header (as per paper Section 2.2)
        if layer == 0 or sampling_idx == 3 or bitrate_idx == 0 or bitrate_idx == 15:
            return None
        
        # Bitrate table (simplified for MPEG1 Layer 3)
        bitrates = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0]
        sample_rates = [44100, 48000, 32000, 0]
        
        if version == 3:  # MPEG1
            bitrate = bitrates[bitrate_idx] * 1000
            sample_rate = sample_rates[sampling_idx]
        else:
            return None  # Simplified - only handle MPEG1
        
        if sample_rate == 0 or bitrate == 0:
            return None
        
        # Calculate frame size using paper's equation (1)
        frame_size = (144 * bitrate // sample_rate) + padding
        
        return {
            'frame_size': frame_size,
            'bitrate': bitrate,
            'sample_rate': sample_rate,
            'padding': padding,
            'header_size': 4  # Header is always 4 bytes
        }

    def _read_file_to_hide(self, file_path: str) -> bytes:
        """
        Read and prepare file for embedding with signature
        """
        try:
            with open(file_path, "rb") as f:
                file_data = f.read()
            
            filename = os.path.basename(file_path)
            filename_bytes = filename.encode("utf-8")
            
            filename_len = len(filename_bytes)
            file_size = len(file_data)
            checksum = hashlib.md5(file_data).digest()
            
            # Create header
            header = struct.pack("<HI16s", filename_len, file_size, checksum)
            header += filename_bytes
            
            # Add signatures
            start_sig, end_sig = self.signatures.get(self.bits_per_sample, (0, 0))
            start_bytes = struct.pack(">H", start_sig)
            end_bytes = struct.pack(">H", end_sig)
            
            complete_data = start_bytes + header + file_data + end_bytes
            
            return complete_data
            
        except Exception as e:
            raise IOError(f"Error reading file: {str(e)}")

    def _data_to_bits(self, data: bytes) -> List[int]:
        """Convert bytes to bits"""
        bits = []
        for byte in data:
            for i in range(8):
                bits.append((byte >> (7 - i)) & 1)
        return bits

    def _bits_to_data(self, bits: List[int]) -> bytes:
        """Convert bits to bytes"""
        data = bytearray()
        for i in range(0, len(bits), 8):
            if i + 7 < len(bits):
                byte = 0
                for j in range(8):
                    byte |= bits[i + j] << (7 - j)
                data.append(byte)
        return bytes(data)

    def hide_file(self, mp3_path: str, file_to_hide_path: str, output_path: str) -> None:
        """
        Hide file in MP3 by modifying LSBs of audio data in frames
        """
        print(f"Reading MP3 file: {mp3_path}")
        with open(mp3_path, 'rb') as f:
            mp3_data = bytearray(f.read())
        
        print("Analyzing MP3 frame structure...")
        frames = self._find_mp3_frames(mp3_data)
        print(f"Found {len(frames)} MP3 frames")
        
        if not frames:
            raise ValueError("No valid MP3 frames found")
        
        # Calculate embedding capacity
        total_audio_bytes = sum(frame[1] - frame[2]['header_size'] for frame in frames)
        capacity_bits = total_audio_bytes * self.bits_per_sample
        
        print(f"Total audio data: {total_audio_bytes} bytes")
        print(f"Embedding capacity: {capacity_bits} bits")
        
        # Read file to hide
        file_data = self._read_file_to_hide(file_to_hide_path)
        data_bits = self._data_to_bits(file_data)
        
        # Add metadata about embedding position
        metadata = struct.pack("<II", len(file_data), self.bits_per_sample)
        metadata_bits = self._data_to_bits(metadata)
        complete_bits = metadata_bits + data_bits
        
        if len(complete_bits) > capacity_bits:
            raise ValueError(f"File too large. Need {len(complete_bits)} bits, have {capacity_bits}")
        
        print(f"Embedding {len(complete_bits)} bits into MP3 frames...")
        
        # Embed data into frame audio data
        bit_index = 0
        
        for frame_idx, (frame_start, frame_size, header_info) in enumerate(frames):
            if bit_index >= len(complete_bits):
                break
            
            # Skip header, embed in audio data only
            audio_start = frame_start + header_info['header_size']
            audio_end = frame_start + frame_size
            
            # Process audio data bytes
            for byte_pos in range(audio_start, audio_end):
                if bit_index >= len(complete_bits):
                    break
                
                # Get current byte
                current_byte = mp3_data[byte_pos]
                
                # Clear LSBs
                current_byte &= (0xFF << self.bits_per_sample)
                
                # Embed bits
                bits_to_embed = 0
                for i in range(self.bits_per_sample):
                    if bit_index + i < len(complete_bits):
                        bits_to_embed |= complete_bits[bit_index + i] << i
                
                current_byte |= bits_to_embed
                mp3_data[byte_pos] = current_byte
                
                bit_index += self.bits_per_sample
        
        print(f"Writing stego MP3 to: {output_path}")
        with open(output_path, 'wb') as f:
            f.write(mp3_data)
        
        print(f"Successfully embedded {len(file_data)} bytes")
        
        # Calculate and display metrics
        self._calculate_metrics(mp3_path, output_path)

    def extract_file(self, stego_mp3_path: str, output_dir: str = ".") -> str:
        """
        Extract hidden file from stego MP3
        """
        print(f"Reading stego MP3: {stego_mp3_path}")
        with open(stego_mp3_path, 'rb') as f:
            mp3_data = f.read()
        
        print("Analyzing MP3 frame structure...")
        frames = self._find_mp3_frames(mp3_data)
        print(f"Found {len(frames)} MP3 frames")
        
        if not frames:
            raise ValueError("No valid MP3 frames found")
        
        # Extract metadata first
        metadata_bits = []
        bit_count = 0
        needed_bits = 64  # 8 bytes for metadata
        
        for frame_start, frame_size, header_info in frames:
            if bit_count >= needed_bits:
                break
            
            audio_start = frame_start + header_info['header_size']
            audio_end = frame_start + frame_size
            
            for byte_pos in range(audio_start, audio_end):
                if bit_count >= needed_bits:
                    break
                
                current_byte = mp3_data[byte_pos]
                
                for i in range(self.bits_per_sample):
                    if bit_count < needed_bits:
                        metadata_bits.append((current_byte >> i) & 1)
                        bit_count += 1
        
        # Parse metadata
        metadata_bytes = self._bits_to_data(metadata_bits)
        file_length, embedded_bits = struct.unpack("<II", metadata_bytes[:8])
        
        if file_length <= 0 or file_length > 100 * 1024 * 1024:
            raise ValueError(f"Invalid file length: {file_length}")
        
        print(f"Extracting file of {file_length} bytes...")
        
        # Extract file data
        total_bits_needed = 64 + (file_length * 8)
        extracted_bits = []
        bit_count = 0
        
        for frame_start, frame_size, header_info in frames:
            if bit_count >= total_bits_needed:
                break
            
            audio_start = frame_start + header_info['header_size']
            audio_end = frame_start + frame_size
            
            for byte_pos in range(audio_start, audio_end):
                if bit_count >= total_bits_needed:
                    break
                
                current_byte = mp3_data[byte_pos]
                
                for i in range(self.bits_per_sample):
                    if bit_count < total_bits_needed:
                        extracted_bits.append((current_byte >> i) & 1)
                        bit_count += 1
        
        # Skip metadata bits and convert to data
        file_bits = extracted_bits[64:]
        file_data = self._bits_to_data(file_bits)
        
        # Parse file structure
        try:
            # Skip signature
            data_offset = 2
            header_size = struct.calcsize("<HI16s")
            
            filename_len, original_size, checksum = struct.unpack(
                "<HI16s", file_data[data_offset:data_offset + header_size]
            )
            
            data_offset += header_size
            filename = file_data[data_offset:data_offset + filename_len].decode("utf-8")
            data_offset += filename_len
            
            actual_data = file_data[data_offset:data_offset + original_size]
            
            # Verify checksum
            if hashlib.md5(actual_data).digest() != checksum:
                print("Warning: Checksum mismatch")
            
            output_path = os.path.join(output_dir, filename)
            
            with open(output_path, 'wb') as f:
                f.write(actual_data)
            
            print(f"Successfully extracted to: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"Error parsing data: {e}")
            output_path = os.path.join(output_dir, "extracted.bin")
            with open(output_path, 'wb') as f:
                f.write(file_data[:file_length])
            return output_path

    def _calculate_metrics(self, original_path: str, stego_path: str) -> None:
        """Calculate and display quality metrics"""
        with open(original_path, 'rb') as f:
            original = np.frombuffer(f.read(), dtype=np.uint8)
        
        with open(stego_path, 'rb') as f:
            stego = np.frombuffer(f.read(), dtype=np.uint8)
        
        # Calculate bit changes
        min_len = min(len(original), len(stego))
        changes = np.sum(original[:min_len] != stego[:min_len])
        
        print(f"Modified bytes: {changes}")
        print(f"Modification rate: {changes/min_len*100:.4f}%")
