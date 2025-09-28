# mp3_safe_stego.py
import os
from typing import List, Tuple, Set

# Bitrate tables (kbps)
# Index 0 and 15 are invalid/reserved and will be rejected.
# Tables are organized as: [version_key][layer_key][bitrate_index]
# version_key: '1' (MPEG1), '2' (MPEG2/2.5 combined for bitrate usage except sample rate)
# layer_key: 1 -> Layer I, 2 -> Layer II, 3 -> Layer III
_BITRATE_TABLE = {
    '1': {  # MPEG-1
        1: [None, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448, None],
        2: [None, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384, None],
        3: [None, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, None],
    },
    '2': {  # MPEG-2 & 2.5 (uses different table for Layer I vs others)
        1: [None, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256, None],
        2: [None, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, None],
        3: [None, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, None],
    }
}

# Sample rate table by version
_SAMPLE_RATE = {
    '1': [44100, 48000, 32000, None],         # MPEG1
    '2': [22050, 24000, 16000, None],         # MPEG2
    '2.5': [11025, 12000, 8000, None],        # MPEG2.5
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
    if data[0:3] != b'ID3':
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
    h = int.from_bytes(header_bytes, 'big')

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
        version = '2.5'
        version_key = '2'
    elif version_bits == 1:
        return False, {}
    elif version_bits == 2:
        version = '2'
        version_key = '2'
    else:
        version = '1'
        version_key = '1'

    # layer decode
    # 00 -> reserved, 01 -> Layer III, 10 -> Layer II, 11 -> Layer I
    if layer_bits == 0:
        return False, {}
    layer = {1: 3, 2: 2, 3: 1}[layer_bits]  # map bits to layer number (1/2/3)

    # bitrate index check
    if bitrate_index == 0 or bitrate_index == 15:
        return False, {}

    # sample rate
    sample_rates = _SAMPLE_RATE['1'] if version == '1' else (_SAMPLE_RATE['2'] if version == '2' else _SAMPLE_RATE['2.5'])
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
        if version == '1':
            frame_length = int(144000 * bitrate_kbps / sample_rate + padding_bit)
        else:
            # MPEG-2/2.5, layer II/III: uses 72000 scaling for Layer III
            if layer == 3:
                frame_length = int(72000 * bitrate_kbps / sample_rate + padding_bit)
            else:
                frame_length = int(144000 * bitrate_kbps / sample_rate + padding_bit)

    return True, {
        'version': version,
        'layer': layer,
        'bitrate_kbps': bitrate_kbps,
        'sample_rate': sample_rate,
        'padding': padding_bit,
        'protection': protection_bit,
        'frame_length': frame_length
    }


def find_mp3_frames(data: bytes, start_offset: int = 0, min_consec: int = 3, max_scan: int | None  = None) -> List[Tuple[int, int]]:
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
        valid, info = _parse_frame_header(data[pos:pos+4])
        if not valid:
            pos += 1
            continue

        frame_len = info['frame_length']
        # sanity checks
        if frame_len <= 4 or pos + frame_len > n:
            pos += 1
            continue

        # quick validation: check next frame header exists at pos + frame_len
        next_pos = pos + frame_len
        valid2, info2 = (False, {})
        if next_pos + 4 <= limit:
            valid2, info2 = _parse_frame_header(data[next_pos:next_pos+4])

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
                v, inf = _parse_frame_header(data[cur:cur+4])
                if not v:
                    break
                fl = inf['frame_length']
                if fl <= 4 or cur + fl > n:
                    break
                run_len += fl
                count += 1
                cur += fl
            if count >= min_consec:
                # add all frames in the run
                cur2 = run_start
                for _ in range(count):
                    valid_run, info_run = _parse_frame_header(data[cur2:cur2+4])
                    frames.append((cur2, info_run['frame_length']))
                    cur2 += info_run['frame_length']
                pos = cur2
            else:
                # not enough consecutive frames to be confident; just step forward
                frames.append((pos, frame_len))
                pos += frame_len

    return frames


def build_protected_indices(data: bytes) -> Set[int]:
    """
    Returns a set of byte indices that must not be modified.
    By default we protect:
      - The entire ID3v2 tag region at start (if present)
      - The 4-byte header for each MP3 frame found
    You can extend this to include side-info bytes (for layer III), or the first N bytes of each frame.
    """
    protected = set()
    id3_end = find_id3v2_end(data)
    if id3_end > 0:
        protected.update(range(0, id3_end))

    frames = find_mp3_frames(data, start_offset=id3_end, min_consec=3, max_scan=2000000)
    # Add 4 header bytes for each frame
    for fstart, flen in frames:
        for i in range(fstart, min(fstart + 4, len(data))):
            protected.add(i)

    # Optionally: protect more bytes after header for layer III side-info.
    # If you want to protect side-info too (safer for decoders), uncomment below:
    # for fstart, flen in frames:
    #     # typically side-info follows header (length depends on MPEG version & channels)
    #     # a conservative choice: protect next 32 bytes
    #     for i in range(fstart, min(fstart + 4 + 32, len(data))):
    #         protected.add(i)

    return protected


def embed_bytes_skip_headers(carrier_path: str, payload_path: str, output_path: str, bits_per_byte: int = 1):
    """
    Embed payload into carrier by modifying LSBs of bytes, but skip indices returned by build_protected_indices().
    bits_per_byte: how many LSBs in each byte to use (1..4 typical)
    """
    if not (1 <= bits_per_byte <= 4):
        raise ValueError("bits_per_byte must be between 1 and 4")

    with open(carrier_path, "rb") as f:
        carrier = bytearray(f.read())

    with open(payload_path, "rb") as f:
        payload = f.read()

    protected = build_protected_indices(bytes(carrier))
    total_bytes = len(carrier)
    usable_positions = [i for i in range(total_bytes) if i not in protected]
    capacity_bits = len(usable_positions) * bits_per_byte
    payload_bits = len(payload) * 8

    if payload_bits > capacity_bits:
        raise ValueError(f"Payload too big ({len(payload)} bytes), capacity {capacity_bits // 8} bytes available")

    # prepare bit iterator
    def bit_stream(b: bytes):
        for byte in b:
            for bitpos in range(7, -1, -1):
                yield (byte >> bitpos) & 1

    bits = bit_stream(payload)
    mask = (0xFF << bits_per_byte) & 0xFF  # clears the low bits_per_byte

    pos_idx = 0
    for carrier_index in usable_positions:
        # embed bits_per_byte bits into this carrier byte
        bits_val = 0
        for _ in range(bits_per_byte):
            try:
                bits_val = (bits_val << 1) | next(bits)
            except StopIteration:
                # no more bits, write and finish
                carrier[carrier_index] = (carrier[carrier_index] & mask) | bits_val
                with open(output_path, "wb") as out:
                    out.write(carrier)
                return
        carrier[carrier_index] = (carrier[carrier_index] & mask) | bits_val
        pos_idx += 1

    # if we exit the loop with exactly no remaining bits, write out
    with open(output_path, "wb") as out:
        out.write(carrier)


def embed_with_meta(carrier_path: str, payload_path: str, output_path: str, bits_per_byte: int = 1):
    """
    Embed payload with metadata (length + extension) into carrier MP3, skipping headers.
    """
    if not (1 <= bits_per_byte <= 4):
        raise ValueError("bits_per_byte must be between 1 and 4")

    with open(carrier_path, "rb") as f:
        carrier = bytearray(f.read())

    with open(payload_path, "rb") as f:
        payload = f.read()

    ext = os.path.splitext(payload_path)[1].lstrip(".") or "bin"
    ext_bytes = ext.encode("utf-8")
    if len(ext_bytes) > 255:
        raise ValueError("Extension too long")

    header = len(payload).to_bytes(4, "little") + bytes([len(ext_bytes)]) + ext_bytes
    message = header + payload

    protected = build_protected_indices(bytes(carrier))
    usable_positions = [i for i in range(len(carrier)) if i not in protected]
    capacity_bits = len(usable_positions) * bits_per_byte
    if len(message) * 8 > capacity_bits:
        raise ValueError("Message too large for carrier with chosen bits_per_byte")

    def bit_stream(b: bytes):
        for byte in b:
            for bitpos in range(7, -1, -1):
                yield (byte >> bitpos) & 1

    bits = bit_stream(message)
    mask = (0xFF << bits_per_byte) & 0xFF

    for carrier_index in usable_positions:
        bits_val = 0
        for _ in range(bits_per_byte):
            try:
                bits_val = (bits_val << 1) | next(bits)
            except StopIteration:
                carrier[carrier_index] = (carrier[carrier_index] & mask) | bits_val
                with open(output_path, "wb") as out:
                    out.write(carrier)
                print(f"Embedded {len(payload)} bytes with extension .{ext} into {output_path}")
                return
        carrier[carrier_index] = (carrier[carrier_index] & mask) | bits_val


def extract_with_meta(stego_path: str, output_prefix: str, bits_per_byte: int = 1):
    """
    Extract payload with metadata from stego MP3 (header-safe).
    Optimized to avoid slow list.pop(0).
    """
    print(1)
    with open(stego_path, "rb") as f:
        stego = f.read()

    print(2)
    protected = build_protected_indices(stego)
    usable_positions = [i for i in range(len(stego)) if i not in protected]

    print(3)
    # Collect all embedded bits at once
    bit_values = []
    for idx in usable_positions:
        byte_val = stego[idx]
        for bitpos in range(bits_per_byte - 1, -1, -1):
            bit_values.append((byte_val >> bitpos) & 1)

    # Use a cursor instead of popping
    cursor = 0

    print(4)
    def read_bits(n: int) -> int:
        nonlocal cursor
        val = 0
        for _ in range(n):
            val = (val << 1) | bit_values[cursor]
            cursor += 1
        return val

    # --- Metadata ---
    payload_len = 0
    for i in range(4):  # 4 bytes, little-endian
        b = read_bits(8)
        payload_len |= (b << (i * 8))

    print(5)
    ext_len = read_bits(8)
    ext_bytes = bytes(read_bits(8) for _ in range(ext_len))
    ext = ext_bytes.decode("utf-8")

    print(6)
    # --- Payload (fast bulk read) ---
    payload = bytearray(payload_len)
    for i in range(payload_len):
        payload[i] = read_bits(8)

    print(7)
    output_file = f"{output_prefix}.{ext}"
    with open(output_file, "wb") as out:
        out.write(payload)
    print(f"Extracted {len(payload)} bytes → {output_file}")
    return output_file



# Example usage:
if __name__ == "__main__":
    import sys
    op = sys.argv[1]
    carrier = sys.argv[2]
    secret = sys.argv[3]
    out = sys.argv[4]
    # choose bits_per_byte=1 for maximum safety
    if op == "1":
        embed_with_meta(carrier, secret, out, bits_per_byte=1)
        print("Embedding done. Protected header bytes preserved.")
    else:
        extract_with_meta("out1.mp3", "", bits_per_byte=1)
