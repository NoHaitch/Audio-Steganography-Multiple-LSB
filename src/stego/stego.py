import os
from typing import Tuple, Dict
from fileio import reader, writter
from cipher import vigenere_decrypt, vigenere_encrypt


SIGNATURES: Dict[int, Tuple[str, str]] = {
    1: ("10101010101010", "10101010101010"),  # 1bit
    2: ("01010101010101", "01010101010101"),  # 2bit
    3: ("10101010101010", "01010101010101"),  # 3bit
    4: ("01010101010101", "10101010101010"),  # 4bit
}

_BITRATE_TABLE = {
    "1": {  # MPEG-1
        1: [
            None,
            32,
            64,
            96,
            128,
            160,
            192,
            224,
            256,
            288,
            320,
            352,
            384,
            416,
            448,
            None,
        ],
        2: [None, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384, None],
        3: [None, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, None],
    },
    "2": {  # MPEG-2 & 2.5 (uses different table for Layer I vs others)
        1: [None, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256, None],
        2: [None, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, None],
        3: [None, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, None],
    },
}

# Sample rate table by version
_SAMPLE_RATE = {
    "1": [44100, 48000, 32000, None],  # MPEG1
    "2": [22050, 24000, 16000, None],  # MPEG2
    "2.5": [11025, 12000, 8000, None],  # MPEG2.5
}


def _read_syncsafe_int(b: bytes) -> int:
    """Read 4 bytes syncsafe integer used in ID3v2 size (only 7 bits per byte)."""
    if len(b) != 4:
        return 0
    return (b[0] << 21) | (b[1] << 14) | (b[2] << 7) | b[3]


def find_id3v2_end(data: bytes) -> int:
    """
    If an ID3v2 tag is present at the start, return the offset where it ends.
    Otherwise return 0.
    """
    if len(data) < 10:
        return 0
    if data[0:3] != b"ID3":
        return 0
    # ID3v2 header: 10 bytes; bytes 6..9 = size (syncsafe)
    size = _read_syncsafe_int(data[6:10])
    # total size = header(10) + size
    return 10 + size


def _parse_frame_header(header_bytes: bytes) -> Tuple[bool, dict]:
    """
    Parse 4 bytes of MP3 header. Return (valid, info_dict).
    info_dict includes: version_key ('1' or '2'/'2.5'), layer (1/2/3), bitrate_kbps, sample_rate, padding, frame_length
    If invalid, return (False, {}).
    """
    if len(header_bytes) < 4:
        return False, {}
    h = int.from_bytes(header_bytes, "big")

    sync = (h >> 21) & 0x7FF  # 11 bits
    if sync != 0x7FF:
        return False, {}

    version_bits = (h >> 19) & 0x3
    layer_bits = (h >> 17) & 0x3
    protection_bit = (h >> 16) & 0x1
    bitrate_index = (h >> 12) & 0xF
    sample_rate_index = (h >> 10) & 0x3
    padding_bit = (h >> 9) & 0x1

    # version decode
    # 00 -> MPEG 2.5, 01 -> reserved, 10 -> MPEG2, 11 -> MPEG1
    if version_bits == 0:
        version = "2.5"
        version_key = "2"
    elif version_bits == 1:
        return False, {}
    elif version_bits == 2:
        version = "2"
        version_key = "2"
    else:
        version = "1"
        version_key = "1"

    # layer decode
    # 00 -> reserved, 01 -> Layer III, 10 -> Layer II, 11 -> Layer I
    if layer_bits == 0:
        return False, {}
    layer = {1: 3, 2: 2, 3: 1}[layer_bits]  # map bits to layer number (1/2/3)

    # bitrate index check
    if bitrate_index == 0 or bitrate_index == 15:
        return False, {}

    # sample rate
    sample_rates = (
        _SAMPLE_RATE["1"]
        if version == "1"
        else (_SAMPLE_RATE["2"] if version == "2" else _SAMPLE_RATE["2.5"])
    )
    sample_rate = sample_rates[sample_rate_index]
    if sample_rate is None:
        return False, {}

    # bitrate
    bitrates = _BITRATE_TABLE[version_key].get(layer)
    if not bitrates:
        return False, {}
    bitrate_kbps = bitrates[bitrate_index]
    if bitrate_kbps is None:
        return False, {}

    # compute frame length
    if layer == 1:
        # Layer I
        frame_length = int((12 * bitrate_kbps * 1000 / sample_rate + padding_bit) * 4)
    else:
        # Layer II & III
        if version == "1":
            frame_length = int(144000 * bitrate_kbps / sample_rate + padding_bit)
        else:
            # MPEG-2/2.5, layer II/III: uses 72000 scaling for Layer III
            if layer == 3:
                frame_length = int(72000 * bitrate_kbps / sample_rate + padding_bit)
            else:
                frame_length = int(144000 * bitrate_kbps / sample_rate + padding_bit)

    return True, {
        "version": version,
        "layer": layer,
        "bitrate_kbps": bitrate_kbps,
        "sample_rate": sample_rate,
        "padding": padding_bit,
        "protection": protection_bit,
        "frame_length": frame_length,
    }


def find_mp3_frames(
    data: bytes, start_offset: int = 0, min_consec: int = 3, max_scan: int | None = None
) -> list[Tuple[int, int]]:
    """
    Find plausible MP3 frames by scanning for sync words and validating headers.
    Returns list of (frame_offset, frame_length).
    min_consec: require this many consecutive valid frames to increase confidence.
    max_scan: if set, limit scanning to first max_scan bytes after start_offset.
    """
    pos = start_offset
    n = len(data)
    frames = []
    limit = n if max_scan is None else min(n, start_offset + max_scan)

    # We'll use a two-pass: when we see a valid header we tentatively accept it and check the next frame.
    while pos + 4 <= limit:
        # fast sync check: two bytes 0xFF Ex (first 11 bits ones)
        # but we'll call full parser
        valid, info = _parse_frame_header(data[pos : pos + 4])
        if not valid:
            pos += 1
            continue

        frame_len = info["frame_length"]
        # sanity checks
        if frame_len <= 4 or pos + frame_len > n:
            pos += 1
            continue

        # quick validation: check next frame header exists at pos + frame_len
        next_pos = pos + frame_len
        valid2, info2 = (False, {})
        if next_pos + 4 <= limit:
            valid2, info2 = _parse_frame_header(data[next_pos : next_pos + 4])

        if not valid2:
            # try to be tolerant: look ahead a couple of bytes (resync possible)
            # but for our purpose we require min_consec frames to be confident.
            # We'll still accept single frames but continue scanning.
            frames.append((pos, frame_len))
            pos += frame_len
            continue
        else:
            # we have at least two consecutive valid frames; gather a run
            run_start = pos
            run_len = frame_len
            count = 1
            cur = next_pos
            while cur + 4 <= limit:
                v, inf = _parse_frame_header(data[cur : cur + 4])
                if not v:
                    break
                fl = inf["frame_length"]
                if fl <= 4 or cur + fl > n:
                    break
                run_len += fl
                count += 1
                cur += fl
            if count >= min_consec:
                # add all frames in the run
                cur2 = run_start
                for _ in range(count):
                    valid_run, info_run = _parse_frame_header(data[cur2 : cur2 + 4])
                    frames.append((cur2, info_run["frame_length"]))
                    cur2 += info_run["frame_length"]
                pos = cur2
            else:
                # not enough consecutive frames to be confident; just step forward
                frames.append((pos, frame_len))
                pos += frame_len

    return frames


def build_protected_indices(data: bytes) -> set[int]:
    """
    Returns a set of byte indices that must not be modified:
      - The entire ID3v2 tag region at start (if present)
      - The 4-byte header for each MP3 frame found
    """
    protected = set()
    
    # Protect ID3v2 tag if present
    id3_end = find_id3v2_end(data)
    if id3_end > 0:
        protected.update(range(0, id3_end))

    # Find all MP3 frames
    frames = find_mp3_frames(data, start_offset=id3_end, min_consec=3, max_scan=2000000)
    
    for fstart, flen in frames:
        # Protect the entire frame header (4 bytes)
        for i in range(fstart, min(fstart + 4, len(data))):
            protected.add(i)
            
        # For Layer III frames, protect the side information too
        # This is typically 17 bytes for mono, 32 bytes for stereo
        # after the 4-byte header
        if flen > 4:
            # Conservative approach: protect first 36 bytes of each frame
            # This covers header + side info + some scale factors
            protected_end = min(fstart + 36, fstart + flen, len(data))
            for i in range(fstart + 4, protected_end):
                protected.add(i)
                
            # Also protect the last few bytes which might contain ancillary data
            last_protected_start = max(fstart + 4, fstart + flen - 10)
            for i in range(last_protected_start, fstart + flen):
                if i < len(data):
                    protected.add(i)

    return protected


def embed_message(
    mp3_bytes: bytearray, message_bits: str, bits_per_sample: int
) -> bytearray:
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

    data = mp3_bytes[offset:]
    modified = data.copy()

    # Group message bits into chunks of bits_per_sample
    chunks = [
        message_bits[i : i + bits_per_sample]
        for i in range(0, len(message_bits), bits_per_sample)
    ]

    mask = 0xFF ^ ((1 << bits_per_sample) - 1)

    for i, chunk in enumerate(chunks):
        if i >= len(modified):
            break
        chunk = chunk.ljust(bits_per_sample, "0")  # pad last chunk
        bits_val = int(chunk, 2)
        modified[i] = (modified[i] & mask) | bits_val

    return mp3_bytes[:offset] + modified


def string_to_bit_stream(binary_string: str):
    """Convert binary string like '10101010' to individual bit values"""
    for char in binary_string:
        if char in "01":
            yield int(char)


def embed(
    audio_path: str, file_to_hide_path: str, output_path: str, bits_per_sample: int = 2, encrypt: bool = False, key: str | None = None
) -> None:
    """
    Hide a file inside an audio file

    Args:
        audio_path: Cover audio file path
        file_to_hide_path: Path to the file that will be hidden
        output_path: Path where the steganographic audio will be saved

    Raises:
        ValueError: If audio file is too small or files cannot be processed
        IOError: If files cannot be read or written
    """
    if not (1 <= bits_per_sample <= 4):
        raise ValueError("bits_per_sample must be between 1 and 4")

    if bits_per_sample not in SIGNATURES:
        raise ValueError(f"No signature defined for {bits_per_sample} bits per sample")

    if encrypt and key is None:
        raise ValueError("If using encryption, provide the key!")

    # Read files
    carrier = reader.read_mp3_bytes(audio_path)

    message_file = reader.read_secret_file(file_to_hide_path)

    payload = message_file.content

    # Prepare metadata
    ext = os.path.splitext(file_to_hide_path)[1].lstrip(".") or "bin"
    ext_bytes = ext.encode("utf-8")
    if len(ext_bytes) > 255:
        raise ValueError("Extension too long")

    header = len(payload).to_bytes(4, "little") + bytes([len(ext_bytes)]) + ext_bytes

    # Get signatures
    start_signature, end_signature = SIGNATURES[bits_per_sample]

    # Calculate capacity
    protected = build_protected_indices(bytes(carrier))
    usable_positions = [i for i in range(len(carrier)) if i not in protected]

    # Calculate total bits needed
    signature_bits = len(start_signature) + len(end_signature)
    data_bits = (len(header) + len(payload)) * 8
    total_bits = signature_bits + data_bits
    capacity_bits = len(usable_positions) * bits_per_sample

    if encrypt and key is not None:
        payload = vigenere_encrypt(data=payload, key=key)

    print(f"Bits needed: {total_bits}, Capacity: {capacity_bits}")

    if total_bits > capacity_bits:
        raise ValueError(
            f"Message too large: need {total_bits} bits, have {capacity_bits}"
        )

    # Create combined bit stream
    def combined_bit_stream():
        # Start signature bits
        for bit in string_to_bit_stream(start_signature):
            yield bit
        # Header and payload bits
        for byte in header + payload:
            for bitpos in range(7, -1, -1):
                yield (byte >> bitpos) & 1
        # End signature bits
        for bit in string_to_bit_stream(end_signature):
            yield bit

    # Embed
    bits = combined_bit_stream()
    mask = (0xFF << bits_per_sample) & 0xFF

    for carrier_index in usable_positions:
        bits_val = 0
        for _ in range(bits_per_sample):
            try:
                bits_val = (bits_val << 1) | next(bits)
            except StopIteration:
                # Done embedding
                carrier[carrier_index] = (carrier[carrier_index] & mask) | bits_val
                with open(output_path, "wb") as out:
                    out.write(carrier)
                print(
                    f"Embedded {len(payload)} bytes with signatures using {bits_per_sample}-bit LSB"
                )
                return

        carrier[carrier_index] = (carrier[carrier_index] & mask) | bits_val

    # Write final result
    writter.write_mp3_bytes(output_path, carrier)
    print(
        f"Embedded {len(payload)} bytes with signatures using {bits_per_sample}-bit LSB"
    )


def detect_bits_per_sample(stego: bytes, usable_positions: list) -> int:
    """
    Detect the bits_per_sample by looking for signature patterns at the beginning
    of the usable positions.

    Args:
        stego (bytes): The stego audio data
        usable_positions (list): List of usable byte positions (non-protected)

    Returns:
        int: The detected bits_per_sample (1-4), or raises ValueError if not found
    """
    # Try each possible bits_per_sample value
    for bits_per_sample, (start_sig, end_sig) in SIGNATURES.items():
        try:
            # Extract bits from the beginning using this bits_per_sample
            extracted_bits = []

            # We need enough positions to read at least the start signature
            if len(usable_positions) * bits_per_sample < len(start_sig):
                continue

            # Extract bits using the current bits_per_sample hypothesis
            for pos_idx in range(
                len(start_sig) // bits_per_sample
                + (1 if len(start_sig) % bits_per_sample else 0)
            ):
                if pos_idx >= len(usable_positions):
                    break

                byte_val = stego[usable_positions[pos_idx]]
                # Extract the LSBs according to bits_per_sample
                lsb_mask = (1 << bits_per_sample) - 1
                lsb_bits = byte_val & lsb_mask

                # Convert to binary string (most significant bit first)
                for bit_pos in range(bits_per_sample - 1, -1, -1):
                    extracted_bits.append(str((lsb_bits >> bit_pos) & 1))

            # Check if we found the start signature
            extracted_signature = "".join(extracted_bits[: len(start_sig)])
            if extracted_signature == start_sig:
                print(f"Detected signature for {bits_per_sample}-bit LSB steganography")
                return bits_per_sample

        except (IndexError, ValueError):
            continue

    raise ValueError(
        "Could not detect bits_per_sample from signatures. File may not contain embedded data or may be corrupted."
    )


def extract(stego_audio_path: str, output_path: str, encrypted: bool = False, key: str | None = None):
    """
    Extract hidden file from a stego MP3 using signature detection to determine bits_per_sample.

    Args:
        stego_audio_path (str): Path to stego audio file
        output_path (str): Path where the extracted file will be saved
    """
    print("Reading stego audio file...")
    with open(stego_audio_path, "rb") as f:
        stego = f.read()

    print("Building protected indices...")
    protected = build_protected_indices(stego)
    usable_positions = [i for i in range(len(stego)) if i not in protected]

    print("Detecting bits per sample from signature...")
    bits_per_sample = detect_bits_per_sample(stego, usable_positions)
    print(f"Detected {bits_per_sample} bits per sample")

    # Create bit extraction function
    def extract_bits_from_position(pos_idx: int, bits_count: int) -> int:
        """Extract bits_count LSBs from the byte at usable_positions[pos_idx]"""
        if pos_idx >= len(usable_positions):
            return 0
        byte_val = stego[usable_positions[pos_idx]]
        lsb_mask = (1 << bits_count) - 1
        return byte_val & lsb_mask

    # Skip the start signature
    start_sig_length = len(SIGNATURES[bits_per_sample][0])
    signature_positions_used = (
        start_sig_length + bits_per_sample - 1
    ) // bits_per_sample

    current_pos_idx = signature_positions_used

    def read_bits(n: int) -> int:
        """Read n bits from the current position"""
        nonlocal current_pos_idx
        val = 0
        bits_read = 0

        while bits_read < n:
            if current_pos_idx >= len(usable_positions):
                raise ValueError("Unexpected end of data while reading bits")

            # How many bits can we read from current position?
            bits_available = bits_per_sample
            bits_needed = n - bits_read
            bits_to_take = min(bits_available, bits_needed)

            # Extract LSBs from current position
            lsb_value = extract_bits_from_position(current_pos_idx, bits_per_sample)

            # Take only the bits we need (from MSB side of the extracted value)
            if bits_to_take < bits_per_sample:
                # Shift right to get the MSB bits
                bits_value = lsb_value >> (bits_per_sample - bits_to_take)
            else:
                bits_value = lsb_value

            # Add to our result
            val = (val << bits_to_take) | bits_value
            bits_read += bits_to_take

            # If we used all bits from this position, move to next
            if bits_to_take == bits_per_sample:
                current_pos_idx += 1
            else:
                # We only used part of this position's bits
                # For simplicity, we'll still move to next position
                # In a more sophisticated implementation, you'd track partial usage
                current_pos_idx += 1

        return val

    print("Reading metadata...")

    # Read payload length (4 bytes, little-endian)
    payload_len = 0
    for i in range(4):
        b = read_bits(8)
        payload_len |= b << (i * 8)

    print(f"Payload length: {payload_len} bytes")

    # Read extension length
    ext_len = read_bits(8)

    # Read extension
    ext_bytes = bytes(read_bits(8) for _ in range(ext_len))
    ext = ext_bytes.decode("utf-8")

    print(f"File extension: .{ext}")

    # Read payload
    print("Reading payload...")
    payload = bytearray(payload_len)
    for i in range(payload_len):
        payload[i] = read_bits(8)

    # Look for end signature to verify extraction
    print("Verifying end signature...")
    end_sig = SIGNATURES[bits_per_sample][1]
    try:
        extracted_end_bits = []
        end_sig_positions = (len(end_sig) + bits_per_sample - 1) // bits_per_sample

        for _ in range(end_sig_positions):
            if current_pos_idx >= len(usable_positions):
                break
            lsb_value = extract_bits_from_position(current_pos_idx, bits_per_sample)
            for bit_pos in range(bits_per_sample - 1, -1, -1):
                extracted_end_bits.append(str((lsb_value >> bit_pos) & 1))
            current_pos_idx += 1

        extracted_end_signature = "".join(extracted_end_bits[: len(end_sig)])
        if extracted_end_signature == end_sig:
            print("End signature verified successfully!")
        else:
            print("Warning: End signature not found or corrupted")
    except Exception as e:
        print(f"Warning: Could not verify end signature: {e}")

    # Write output file
    output_file = f"{output_path}.{ext}"
    with open(output_file, "wb") as out:
        out.write(payload)

    print(f"Extracted {len(payload)} bytes → {output_file}")
    return output_file
