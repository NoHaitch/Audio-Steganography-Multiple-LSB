import os
from utils.types import MessageData


class StegoInputError(Exception):
    """ Stego Input Exceptions. """
    pass


def read_secret_file(path: str) -> MessageData:
    """ Reads any file in binary mode and returns its content and metadata. """
    if not os.path.exists(path):
        raise StegoInputError(f"Secret file not found at path: {path}")

    try:
        # File metadata
        file_size = os.path.getsize(path)
        _, file_extension = os.path.splitext(path)

        # Read as binary
        with open(path, "rb") as f:
            file_content = f.read()

        if len(file_content) != file_size:
            raise StegoInputError(
                f"Mismatch in file size for {path}. "
                f"Expected {file_size} bytes, but read {len(file_content)}."
            )

        return MessageData(
            content=file_content, size_in_bytes=file_size, extension=file_extension
        )

    except IOError as e:
        raise StegoInputError(f"Could not read the secret message file at {path}: {e}") from e
    except Exception as e:
        raise StegoInputError(
            f"An unexpected error occurred while reading {path}: {e}"
        ) from e
