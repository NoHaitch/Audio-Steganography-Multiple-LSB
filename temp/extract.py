INPUT_FILE = "../test/result.mp3"

START_SIG = "10101010101010"
END_SIG = "10101010101010"

def read_mp3_bytes(path):
    with open(path, "rb") as f:
        return bytearray(f.read())

def extract_message(mp3_bytes):
    # Skip ID3 if present
    if mp3_bytes[0:3] == b"ID3":
        tag_size = (mp3_bytes[6] << 21) | (mp3_bytes[7] << 14) | (mp3_bytes[8] << 7) | mp3_bytes[9]
        offset = 10 + tag_size
    else:
        offset = 0

    data = mp3_bytes[offset:]
    bits = "".join([str(byte & 1) for byte in data])

    start_idx = bits.find(START_SIG)
    end_idx = bits.find(END_SIG, start_idx + len(START_SIG))

    if start_idx == -1 or end_idx == -1:
        return None
    return bits[start_idx + len(START_SIG):end_idx]

if __name__ == "__main__":
    mp3_bytes = read_mp3_bytes(INPUT_FILE)
    message = extract_message(mp3_bytes)

    if message:
        print("Extracted message:", message)
    else:
        print("No hidden message found.")
