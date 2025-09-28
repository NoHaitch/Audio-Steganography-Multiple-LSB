from dataclasses import dataclass


@dataclass
class SecretFile:
    name: str
    extension: str
    size: int
    content: bytes
