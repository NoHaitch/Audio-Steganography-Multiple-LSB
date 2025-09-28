from itertools import cycle


def vigenere_encrypt(data: bytes, key: str) -> bytes:
    """
    Encrypt data using Vigenere cipher with the given key.
    Works on arbitrary binary data.
    """
    key_bytes = key.encode("utf-8")
    return bytes((b + k) % 256 for b, k in zip(data, cycle(key_bytes)))


def vigenere_decrypt(data: bytes, key: str) -> bytes:
    """
    Decrypt data encrypted with Vigenere cipher.
    Works on arbitrary binary data.
    """
    key_bytes = key.encode("utf-8")
    return bytes((b - k) % 256 for b, k in zip(data, cycle(key_bytes)))
