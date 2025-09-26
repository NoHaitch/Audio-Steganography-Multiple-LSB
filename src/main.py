import argparse
import sys
from audio import play_audio
from audio.player import AudioPlayerError

"""
List of Args
  -h, --help  show this help message and exit
  -play FILE  Play an MP3 or WAV file 
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="MP3 Steganography using Multiple LSB")
    parser.add_argument(
        "-play",
        metavar="FILE",
        help="Play an MP3 or WAV file with the system's default player",
    )

    args = parser.parse_args()

    if args.play:
        try:
            play_audio(args.play)
        except AudioPlayerError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            # Fallback in case some unexpected error happens
            print(f"[FATAL] Unexpected error: {e}", file=sys.stderr)
            sys.exit(2)


if __name__ == "__main__":
    main()
