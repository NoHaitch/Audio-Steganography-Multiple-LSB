import os
from typing import Tuple, Dict
from randomizer.randomize_position import generate_random_position
from fileio import reader, writter
from cipher import vigenere_decrypt, vigenere_encrypt


# Marker to let program know which n-bits used in LSB, so if program want to extract hidden file,
# they will use this reference
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
    { version_key ('1' or '2'/'2.5'), layer (1/2/3), bitrate_kbps, sample_rate, padding, frame_length }
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
    Find MP3 frames by scanning sync words and validating headers
    Return list of (frame_offset, frame_length)
    min_consec: require this many consecutive valid frames to increase confidence
    max_scan: if set, limit scanning to first max_scan bytes after start_offset
    """
    pos = start_offset
    n = len(data)
    frames = []
    limit = n if max_scan is None else min(n, start_offset + max_scan)

    # Check if see a valid header then check the next frame
    while pos + 4 <= limit:
        # fast sync check: two bytes 0xFF Ex (first 11-bits)
        # after that full parser
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
        valid2, _ = (False, {})
        if next_pos + 4 <= limit:
            valid2, _ = _parse_frame_header(data[next_pos : next_pos + 4])

        if not valid2:
            # try to be tolerant: look ahead a couple of bytes (resync possible)
            # but for our purpose we require min_consec frames to be confident
            # We'll still accept single frames but continue scanning
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
                    _, info_run = _parse_frame_header(data[cur2 : cur2 + 4])
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
    audio_path: str,
    file_to_hide_path: str,
    output_path: str,
    bits_per_sample: int = 2,
    encrypt: bool = False,
    key: str | None = None,
    random_position: bool = False,
) -> None:
    """
    Hide a file inside an audio file with optional Vigenere encryption

    Args:
        audio_path: Cover audio file path
        file_to_hide_path: Path to the file that will be hidden
        output_path: Path where the steganographic audio will be saved
        bits_per_sample: Number of LSBs to use for embedding (1-4)
        encrypt: Whether to encrypt the payload using Vigenère cipher
        key: Key for encryption/decryption and randomization
        random_position: Whether to use randomized starting position for embedding

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

    if random_position and key is None:
        raise ValueError("If using random position, provide the key!")

    # Read files
    carrier = reader.read_mp3_bytes(audio_path)
    message_file = reader.read_secret_file(file_to_hide_path)
    payload = message_file.content

    # Extract filename (just the name, not the full path)
    filename = os.path.basename(file_to_hide_path)
    filename_bytes = filename.encode("utf-8")

    if len(filename_bytes) > 255:
        raise ValueError("Filename too long (max 255 bytes)")

    # IMPORTANT: Encrypt payload BEFORE creating header
    # The header should contain the encrypted payload length, not original length
    if encrypt and key is not None:
        print("Encrypting payload...")
        payload = vigenere_encrypt(data=payload, key=key)
        print(f"Encrypted payload length: {len(payload)} bytes")

    # Create header with filename
    # Structure: [payload_length: 4 bytes][filename_length: 1 byte][filename: N bytes]
    # NOTE: payload_length is AFTER encryption
    header = (
        len(payload).to_bytes(4, "little")
        + bytes([len(filename_bytes)])
        + filename_bytes
    )

    print(f"Embedding file: {filename}")
    print(f"Filename length: {len(filename_bytes)} bytes")
    print(f"Payload length: {len(payload)} bytes")

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
        # Header and payload bits (payload is already encrypted if encrypt=True)
        for byte in header + payload:
            for bitpos in range(7, -1, -1):
                yield (byte >> bitpos) & 1
        # End signature bits
        for bit in string_to_bit_stream(end_signature):
            yield bit

    # Handle random positioning if enabled
    start_offset = 0
    if random_position and key is not None:
        start_offset = generate_random_position(key, len(usable_positions))
        print(f"Using randomized starting position: {start_offset}")

    # Embed using circular indexing
    bits = combined_bit_stream()
    mask = (0xFF << bits_per_sample) & 0xFF

    position_index = 0  # Index into usable_positions array
    total_positions = len(usable_positions)

    for _ in range(total_positions):  # Maximum iterations to prevent infinite loop
        # Calculate actual position with circular wrapping
        actual_position_index = (start_offset + position_index) % total_positions
        carrier_index = usable_positions[actual_position_index]

        bits_val = 0
        for _ in range(bits_per_sample):
            try:
                bits_val = (bits_val << 1) | next(bits)
            except StopIteration:
                carrier[carrier_index] = (carrier[carrier_index] & mask) | bits_val
                writter.write_mp3_bytes(output_path, carrier)
                encrypt_status = "with encryption" if encrypt else "without encryption"
                print(
                    f"Successfully embedded '{os.path.basename(file_to_hide_path)}' ({len(payload)} bytes) {encrypt_status}"
                )
                print(f"Using {bits_per_sample}-bit LSB steganography")
                if random_position:
                    print(
                        f"Data embedded with circular wrapping from position {start_offset}"
                    )
                return

        carrier[carrier_index] = (carrier[carrier_index] & mask) | bits_val
        position_index += 1

    # Write final result
    writter.write_mp3_bytes(output_path, carrier)
    encrypt_status = "with encryption" if encrypt else "without encryption"
    print(f"Successfully embedded '{filename}' ({len(payload)} bytes) {encrypt_status}")
    print(f"Using {bits_per_sample}-bit LSB steganography")


def detect_bits_per_sample(
    stego: bytes,
    usable_positions: list,
    random_position: bool = False,
    key: str | None = None,
) -> int:
    """
    Detect the bits_per_sample by looking for signature patterns at the beginning
    of the usable positions

    Args:
        stego (bytes): The stego audio data
        usable_positions (list): List of usable byte positions (non-protected)
        random_position (bool): Whether randomized starting position was used
        key (str): Key for randomization

    Returns:
        int: The detected bits_per_sample (1-4), or raises ValueError if not found
    """
    # Calculate starting offset for circular indexing
    start_offset = 0
    if random_position and key is not None:
        start_offset = generate_random_position(key, len(usable_positions))

    total_positions = len(usable_positions)

    # Try each possible bits_per_sample value
    for bits_per_sample, (start_sig, end_sig) in SIGNATURES.items():
        try:
            # Extract bits from the beginning using this bits_per_sample
            extracted_bits = []

            # We need enough positions to read at least the start signature
            if total_positions * bits_per_sample < len(start_sig):
                continue

            # Extract bits using circular indexing
            bits_needed = len(start_sig)
            positions_needed = (bits_needed + bits_per_sample - 1) // bits_per_sample

            for pos_idx in range(positions_needed):
                if pos_idx >= total_positions:
                    break

                # Calculate actual position with circular wrapping
                actual_position_index = (start_offset + pos_idx) % total_positions
                byte_val = stego[usable_positions[actual_position_index]]

                # Extract the LSBs according to bits_per_sample
                lsb_mask = (1 << bits_per_sample) - 1
                lsb_bits = byte_val & lsb_mask

                # Convert to binary string and add to extracted bits
                for bit_pos in range(bits_per_sample - 1, -1, -1):
                    if len(extracted_bits) < bits_needed:
                        bit_val = (lsb_bits >> bit_pos) & 1
                        extracted_bits.append(str(bit_val))

            # Check if we found the start signature
            extracted_signature = "".join(extracted_bits[: len(start_sig)])
            if extracted_signature == start_sig:
                return bits_per_sample

        except (IndexError, ValueError):
            continue

    raise ValueError(
        "Could not detect bits_per_sample from signatures. File may not contain embedded data or may be corrupted."
    )


def extract(
    stego_audio_path: str,
    output_path: str,
    encrypted: bool = False,
    key: str | None = None,
    random_position: bool = False,
) -> str:
    """
    Extract hidden file from a stego MP3 with automatic decryption if needed

    Args:
        stego_audio_path (str): Path to stego audio file
        output_path (str): Directory w
here the extracted file will be saved
        encrypted (bool): Whether the payload was encrypted
        key (str): Key for decryption and randomization
        random_position (bool): Whether randomized starting position was used

    Returns:
        str: Full path to the extracted file
    """
    if encrypted and key is None:
        raise ValueError("If payload is encrypted, provide the key for decryption!")

    print("Reading stego audio file...")
    stego = reader.read_mp3_bytes(stego_audio_path)

    print("Building protected indices...")
    protected = build_protected_indices(stego)
    usable_positions = [i for i in range(len(stego)) if i not in protected]

    print("Detecting bits per sample from signature...")
    bits_per_sample = detect_bits_per_sample(
        stego, usable_positions, random_position, key
    )
    print(f"Detected {bits_per_sample} bits per sample")

    # Calculate starting offset for circular indexing
    start_offset = 0
    if random_position and key is not None:
        start_offset = generate_random_position(key, len(usable_positions))
        print(f"Using randomized starting position: {start_offset}")

    # Create bit stream generator with circular indexing
    def bit_stream_generator():
        position_index = 0
        total_positions = len(usable_positions)

        while True:  # Generator that can handle circular wrapping
            # Calculate actual position with circular wrapping
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

    # Skip the start signature
    start_sig_length = len(SIGNATURES[bits_per_sample][0])
    try:
        for _ in range(start_sig_length):
            next(bit_gen)
    except StopIteration as e:
        raise ValueError("File is too short to contain a valid signature.") from e

    # Helper function to read bits
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

    print("Reading metadata...")

    # Read payload length (4 bytes, little-endian)
    # NOTE: This is the ENCRYPTED payload length if encryption was used
    payload_len = 0
    for i in range(4):
        b = read_bits(8)
        payload_len |= b << (i * 8)

    print(f"Payload length: {payload_len} bytes")

    # Read filename length
    filename_len = read_bits(8)
    print(f"Filename length: {filename_len} bytes")

    # Read filename
    filename_bytes = bytes(read_bits(8) for _ in range(filename_len))

    # Try to decode filename as UTF-8
    try:
        filename = filename_bytes.decode("utf-8")
        print(f"Original filename: {filename}")
    except UnicodeDecodeError:
        # Fallback to a generic name if decoding fails
        filename = "extracted_file.bin"
        print(f"Warning: Could not decode filename, using '{filename}'")

    # Read payload (still encrypted at this point if encryption was used)
    print("Reading payload...")
    payload = bytearray(payload_len)
    for i in range(payload_len):
        payload[i] = read_bits(8)

    # Decrypt payload AFTER reading it
    if encrypted and key is not None:
        print("Decrypting payload...")
        payload = vigenere_decrypt(data=payload, key=key)
        print(f"Decrypted payload length: {len(payload)} bytes")

    # Verify end signature (optional)
    print("Verifying end signature...")
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
            print("End signature verified successfully")
        else:
            print("⚠ Warning: End signature mismatch (file may still be valid)")
    except Exception as e:
        print(f"Could not verify end signature: {e}")

    # Ensure output directory exists
    os.makedirs(output_path, exist_ok=True)

    # Construct full output path with original filename
    output_file = os.path.join(output_path, filename)

    # Handle filename conflicts
    if os.path.exists(output_file):
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(output_file):
            output_file = os.path.join(output_path, f"{base}_{counter}{ext}")
            counter += 1
        print(f"⚠ File exists, saving as: {os.path.basename(output_file)}")

    # Write output file
    with open(output_file, "wb") as out:
        out.write(payload)

    print(f"✓ Extracted {len(payload)} bytes → {output_file}")
    return output_file
