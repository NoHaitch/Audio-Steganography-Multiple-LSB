class StegoError(Exception):
    """Base exception for all steganography-related errors."""


class IOReaderError(StegoError):
    """ Raised when reading an MP3 file fails or file is invalid. """


class IOWriterError(StegoError):
    """ Raised when writing an MP3 file fails. """
