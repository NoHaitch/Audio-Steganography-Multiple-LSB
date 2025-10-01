import os
from typing import Tuple, Dict
from randomizer.randomize_position import generate_random_position
from fileio import reader, writter
from cipher import vigenere_decrypt, vigenere_encrypt


# Marker to let program know which n-bits used in LSB, so the extractor know
SIGNATURES: Dict[int, Tuple[str, str]] = {
    1: ("10101010101010", "10101010101010"),  # 1bit
    2: ("01010101010101", "01010101010101"),  # 2bit
    3: ("10101010101010", "01010101010101"),  # 3bit
    4: ("01010101010101", "10101010101010"),  # 4bit
}

# Show how many data used each second
BITRATE_TABLE = {
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
    "2": {  # MPEG-2, 2.5
        1: [None, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256, None],
        2: [None, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, None],
        3: [None, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, None],
    },
}

# Sample rate
SAMPLE_RATE = {
    "1": [44100, 48000, 32000, None],  # MPEG1
    "2": [22050, 24000, 16000, None],  # MPEG2
    "2.5": [11025, 12000, 8000, None],  # MPEG2.5
}


def calculate_syncsafe(b: bytes) -> int:
    """
    Calculate the size of the ID3v2 tag. Only use 7 bits per byte (1 bit MSB not used).
    Syncsafe implemented to prevent existence of pattern 0xFF (1111 1111) because it is marker
    of the beginning of audio frame

    Args:
        b (bytes)

    Returns:
        int: size of the ID3v2 tag
    """
    if len(b) != 4:
        return 0
    return (b[0] << 21) | (b[1] << 14) | (b[2] << 7) | b[3]


def find_id3v2_end(data: bytes) -> int:
    """
    If an ID3v2 tag is present at the start, return the offset where it ends
    Otherwise return 0

    Args:
        data (bytes)

    Returns:
        int: offset of the MP3 where ID3v2 finished
    """
    if len(data) < 10:
        return 0
    if data[0:3] != b"ID3":
        return 0
    # ID3v2 header: 10 bytes; bytes 6..9 = size (syncsafe)
    size = calculate_syncsafe(data[6:10])
    # total size = header(10) + size
    return 10 + size


def _parse_frame_header(header_bytes: bytes) -> Tuple[bool, dict]:
    """
    Parse 4 bytes of MP3 header
    {version_key ('1', '2'/'2.5'), layer (1/2/3), bitrate_kbps, sample_rate, padding, frame_length}
    """
    if len(header_bytes) < 4:
        return False, {}
    h = int.from_bytes(header_bytes, "big")

    sync = (h >> 21) & 0x7FF  # 11-bit
    if sync != 0x7FF:
        return False, {}

    version_bits = (h >> 19) & 0x3
    layer_bits = (h >> 17) & 0x3
    protection_bit = (h >> 16) & 0x1
    bitrate_index = (h >> 12) & 0xF
    sample_rate_index = (h >> 10) & 0x3
    padding_bit = (h >> 9) & 0x1

    # Version decode: 00: MPEG 2.5, 01: reserved, 10: MPEG2, 11: MPEG1
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

    # Layer decode: 00: reserved, 01: Layer 3, 10: Layer 2, 11: Layer 1
    if layer_bits == 0:
        return False, {}
    layer = {1: 3, 2: 2, 3: 1}[layer_bits]

    if bitrate_index == 0 or bitrate_index == 15:
        return False, {}

    sample_rates = (
        SAMPLE_RATE["1"]
        if version == "1"
        else (SAMPLE_RATE["2"] if version == "2" else SAMPLE_RATE["2.5"])
    )
    sample_rate = sample_rates[sample_rate_index]
    if sample_rate is None:
        return False, {}

    bitrates = BITRATE_TABLE[version_key].get(layer)
    if not bitrates:
        return False, {}
    bitrate_kbps = bitrates[bitrate_index]
    if bitrate_kbps is None:
        return False, {}

    if layer == 1:
        # Layer 1
        frame_length = int((12 * bitrate_kbps * 1000 / sample_rate + padding_bit) * 4)
    else:
        # Layer 2 3
        if version == "1":
            frame_length = int(144000 * bitrate_kbps / sample_rate + padding_bit)
        else:
            # MPEG2/MPEG2.5
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
    Find MP3 frames by finding sync words and validating headers
    Return list of (frame_offset, frame_length)
    min_consec: require this many consecutive valid frames
    max_scan: if set, limit finding to first max_scan bytes after start_offset
    """
    pos = start_offset
    n = len(data)
    frames = []
    limit = n if max_scan is None else min(n, start_offset + max_scan)

    # Check if see a valid header
    while pos + 4 <= limit:
        # fast sync check: two bytes 0xFF (first 11-bits)
        valid, info = _parse_frame_header(data[pos : pos + 4])
        if not valid:
            pos += 1
            continue

        frame_len = info["frame_length"]
        # sanity checks
        if frame_len <= 4 or pos + frame_len > n:
            pos += 1
            continue

        # check next frame header exists at pos + frame_len
        next_pos = pos + frame_len
        valid2, _ = (False, {})
        if next_pos + 4 <= limit:
            valid2, _ = _parse_frame_header(data[next_pos : next_pos + 4])

        if not valid2:
            frames.append((pos, frame_len))
            pos += frame_len
            continue
        else:
            # at least two consecutive valid frames (1111 1111), then run
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
                cur2 = run_start
                for _ in range(count):
                    _, info_run = _parse_frame_header(data[cur2 : cur2 + 4])
                    frames.append((cur2, info_run["frame_length"]))
                    cur2 += info_run["frame_length"]
                pos = cur2
            else:
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

    # Protect ID3v2 tag
    id3_end = find_id3v2_end(data)
    if id3_end > 0:
        protected.update(range(0, id3_end))

    frames = find_mp3_frames(data, start_offset=id3_end, min_consec=3, max_scan=2000000)

    for fstart, flen in frames:
        # Protect frame header (4 bytes)
        for i in range(fstart, min(fstart + 4, len(data))):
            protected.add(i)

        # For Layer 3 frames, protect the side information
        # Mono: 17 bytes, stereo: 32 bytes
        # after the 4-byte header
        if flen > 4:
            # header + side info + scale factors
            protected_end = min(fstart + 36, fstart + flen, len(data))
            for i in range(fstart + 4, protected_end):
                protected.add(i)

            last_protected_start = max(fstart + 4, fstart + flen - 10)
            for i in range(last_protected_start, fstart + flen):
                if i < len(data):
                    protected.add(i)

    return protected


def string_to_bit_stream(binary_string: str):
    """Convert binary string to bit"""
    for char in binary_string:
        if char in "01":
            yield int(char)


def embed(
    audio_path: str,
    file_to_hide_path: str,
    output_path: str,
    bits_per_sample: int = 2,
    encrypt: bool | None = False,
    key: str | None = None,
    random_position: bool | None = False,
) -> None:
    """
    Hide a file inside an audio file

    Args:
        audio_path: Cover audio file path
        file_to_hide_path: Path to the file that will be hidden
        output_path: Path output will be saved
        bits_per_sample: Number of LSB to use for embedding (1-4)
        encrypt: encrypt the payload
        key: Key for encryption/decryption and randomization
        random_position: Use randomized starting position

    Raises:
        ValueError: If audio file is too small or files cannot be processed
        IOError: If files cannot be read or written
    """
    if not (1 <= bits_per_sample <= 4):
        raise ValueError("LSB bit must be between 1 and 4")

    if bits_per_sample not in SIGNATURES:
        raise ValueError(f"No signature defined for {bits_per_sample} bits per sample")

    if encrypt and key is None:
        raise ValueError("If using encryption, provide the key")

    if random_position and key is None:
        raise ValueError("If using random position, provide the key")

    # Import
    carrier = reader.read_mp3_bytes(audio_path)
    message_file = reader.read_secret_file(file_to_hide_path)
    payload = message_file.content

    filename = os.path.basename(file_to_hide_path)
    filename_bytes = filename.encode("utf-8")

    if len(filename_bytes) > 255:
        raise ValueError("Filename too long (max 255 bytes)")

    if encrypt and key is not None:
        payload = vigenere_encrypt(data=payload, key=key)
        print(f"Encrypted payload length: {len(payload)} bytes")


    # header: [payload_length: 4 bytes][filename_length: 1 byte][filename: N bytes]
    # payload is after encryption
    header = (
        len(payload).to_bytes(4, "little")
        + bytes([len(filename_bytes)])
        + filename_bytes
    )

    print(f"Embedding file: {filename}")
    print(f"Filename length: {len(filename_bytes)} bytes")
    print(f"Payload length: {len(payload)} bytes")

    start_signature, end_signature = SIGNATURES[bits_per_sample]

    protected = build_protected_indices(bytes(carrier))
    usable_positions = [i for i in range(len(carrier)) if i not in protected]

    signature_bits = len(start_signature) + len(end_signature)
    data_bits = (len(header) + len(payload)) * 8
    total_bits = signature_bits + data_bits
    capacity_bits = len(usable_positions) * bits_per_sample

    print(f"Bits needed: {total_bits}, Capacity: {capacity_bits}")

    if total_bits > capacity_bits:
        raise ValueError(
            f"Message too large: need {total_bits} bits, have {capacity_bits}"
        )

    def combined_bit_stream():
        for bit in string_to_bit_stream(start_signature):
            yield bit
        for byte in header + payload:
            for bitpos in range(7, -1, -1):
                yield (byte >> bitpos) & 1
        # End signature bits
        for bit in string_to_bit_stream(end_signature):
            yield bit

    # Random start positioning
    start_offset = 0
    if random_position and key is not None:
        start_offset = generate_random_position(key, len(usable_positions))
        print(f"Using randomized starting position: {start_offset}")

    # Circular embed case
    bits = combined_bit_stream()
    mask = (0xFF << bits_per_sample) & 0xFF

    position_index = 0
    total_positions = len(usable_positions)
    embedding_complete = False

    for _ in range(total_positions):
        actual_position_index = (start_offset + position_index) % total_positions
        carrier_index = usable_positions[actual_position_index]

        bits_val = 0
        for _ in range(bits_per_sample):
            try:
                bits_val = (bits_val << 1) | next(bits)
            except StopIteration:
                carrier[carrier_index] = (carrier[carrier_index] & mask) | bits_val
                embedding_complete = True
                break

        carrier[carrier_index] = (carrier[carrier_index] & mask) | bits_val
        position_index += 1
        
        if embedding_complete:
            break

    # Write
    writter.write_mp3_bytes(output_path, carrier)
    print(f"Successfully embedded '{os.path.basename(file_to_hide_path)}' ({len(payload)} bytes)")


def detect_bits_per_sample(
    stego: bytes,
    usable_positions: list,
    random_position: bool = False,
    key: str | None = None,
) -> int:
    """
    Detect the LSB bit used from signature in the file

    Args:
        stego (bytes): The stego audio data
        usable_positions (list): List of usable byte positions (non-protected)
        random_position (bool): Whether randomized starting position was used
        key (str): Key for randomization

    Returns:
        int: The detected LSB bit (1-4), or raises ValueError if not found
    """
    start_offset = 0
    if random_position and key is not None:
        start_offset = generate_random_position(key, len(usable_positions))

    total_positions = len(usable_positions)

    for bits_per_sample, (start_sig, end_sig) in SIGNATURES.items():
        try:
            extracted_bits = []

            if total_positions * bits_per_sample < len(start_sig):
                continue

            bits_needed = len(start_sig)
            positions_needed = (bits_needed + bits_per_sample - 1) // bits_per_sample

            for pos_idx in range(positions_needed):
                if pos_idx >= total_positions:
                    break

                actual_position_index = (start_offset + pos_idx) % total_positions
                byte_val = stego[usable_positions[actual_position_index]]

                lsb_mask = (1 << bits_per_sample) - 1
                lsb_bits = byte_val & lsb_mask

                for bit_pos in range(bits_per_sample - 1, -1, -1):
                    if len(extracted_bits) < bits_needed:
                        bit_val = (lsb_bits >> bit_pos) & 1
                        extracted_bits.append(str(bit_val))

            extracted_signature = "".join(extracted_bits[: len(start_sig)])
            if extracted_signature == start_sig:
                return bits_per_sample

        except (IndexError, ValueError):
            continue

    raise ValueError("Could not detect LSB bits")


def extract(
    stego_audio_path: str,
    output_path: str,
    encrypted: bool | None = False,
    key: str | None = None,
    random_position: bool | None = False,
) -> str:
    """
    Extract hidden file from a MP3

    Args:
        stego_audio_path (str): Path to stego audio file
        output_path (str): Directory where the extracted file will be saved
        encrypted (bool): Is the payload was encrypted
        key (str): Key for decryption and randomization
        random_position (bool): Randomized starting position was used

    Returns:
        str: Full path to the extracted file
    """
    if encrypted and key is None:
        raise ValueError("If payload is encrypted, provide the key for decryption")

    if random_position is None:
        random_position = False

    stego = reader.read_mp3_bytes(stego_audio_path)

    print("Finding protected indices")
    protected = build_protected_indices(stego)
    usable_positions = [i for i in range(len(stego)) if i not in protected]

    bits_per_sample = detect_bits_per_sample(
        stego, usable_positions, random_position, key
    )
    print(f"{bits_per_sample} bits LSB")

    # Calculate starting offset
    start_offset = 0
    if random_position and key is not None:
        start_offset = generate_random_position(key, len(usable_positions))
        print(f"Using randomized starting position: {start_offset}")

    def bit_stream_generator():
        position_index = 0
        total_positions = len(usable_positions)

        while True:
            actual_position_index = (start_offset + position_index) % total_positions
            pos = usable_positions[actual_position_index]

            byte_val = stego[pos]
            lsb_mask = (1 << bits_per_sample) - 1
            lsb_bits = byte_val & lsb_mask

            for bit_pos in range(bits_per_sample - 1, -1, -1):
                yield (lsb_bits >> bit_pos) & 1

            position_index += 1
            # Prevent infinite loop - though this should be controlled by caller
            if position_index >= total_positions * 2:  # Allow up to 2 full cycles
                break

    bit_gen = bit_stream_generator()

    start_sig_length = len(SIGNATURES[bits_per_sample][0])
    try:
        for _ in range(start_sig_length):
            next(bit_gen)
    except StopIteration as e:
        raise ValueError("File is too short to contain a valid signature.") from e

    def read_bits(n: int) -> int:
        val = 0
        try:
            for _ in range(n):
                val = (val << 1) | next(bit_gen)
        except StopIteration as e:
            raise ValueError(
                "Unexpected end of data while reading file content."
            ) from e
        return val

    print("Reading metadata")

    # Read payload length (4 bytes, little-endian). Still encrypted
    payload_len = 0
    for i in range(4):
        b = read_bits(8)
        payload_len |= b << (i * 8)

    print(f"Payload length: {payload_len} bytes")

    filename_len = read_bits(8)

    filename_bytes = bytes(read_bits(8) for _ in range(filename_len))

    try:
        filename = filename_bytes.decode("utf-8")
        print(f"Original filename: {filename}")
    except UnicodeDecodeError:
        # Fallback to a generic name if decoding fails
        filename = "extracted_file.bin"
        print(f"Warning: Could not decode filename, using '{filename}'")

    payload = bytearray(payload_len)
    for i in range(payload_len):
        payload[i] = read_bits(8)

    if encrypted and key is not None:
        payload = vigenere_decrypt(data=payload, key=key)
        print(f"Decrypted payload length: {len(payload)} bytes")

    try:
        end_sig = SIGNATURES[bits_per_sample][1]
        extracted_end_bits = []

        for _ in range(len(end_sig)):
            try:
                bit = next(bit_gen)
                extracted_end_bits.append(str(bit))
            except StopIteration:
                break

        extracted_end_signature = "".join(extracted_end_bits)
        if extracted_end_signature == end_sig:
            print("End signature verified")
        else:
            print("Warning: End signature mismatch")
    except Exception as e:
        print(f"Could not verify end signature: {e}")

    os.makedirs(output_path, exist_ok=True)

    output_file = os.path.join(output_path, filename)

    if os.path.exists(output_file):
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(output_file):
            output_file = os.path.join(output_path, f"{base}_{counter}{ext}")
            counter += 1
        print(f"⚠ File exists, saving as: {os.path.basename(output_file)}")

    with open(output_file, "wb") as out:
        out.write(payload)

    print(f"Extracted {len(payload)} bytes → {output_file}")
    return output_file
