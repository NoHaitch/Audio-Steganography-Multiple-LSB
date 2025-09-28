class IOReaderError(Exception):
    """ Raised when reading an MP3 file fails or file is invalid. """

class IOWriterError(Exception):
    """ Raised when writing an MP3 file fails. """

class StegoCompareError(Exception):
    """ Raised when comparing two MP3 files. """
