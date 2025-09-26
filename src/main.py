import argparse
import sys
from audio import play_audio, load_mp3
from audio import AudioPlayerError, AudioIOError


"""
List of Args
  -h, --help          Show this help message and exit
  -play FILE          Play an MP3 or WAV file using system default player
  -read FILE          Read an MP3 file and print decoded PCM samples
    --amount N          Print N samples (default: 20, from the middle)
    --range START END   Print samples from START to END indices
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="MP3 Steganography using Multiple LSB")

    parser.add_argument(
        "-play",
        metavar="FILE",
        help="Play an MP3 or WAV file using system default player.",
    )

    parser.add_argument(
        "-read",
        metavar="FILE",
        help="Read an MP3 file and print decoded PCM samples.",
    )

    parser.add_argument(
        "--amount",
        type=int,
        help="Number of samples to print (default: 50, from the middle of the file).",
    )

    parser.add_argument(
        "--range",
        nargs=2,
        type=int,
        metavar=("START", "END"),
        help="Range of sample indices to print (overrides --amount).",
    )

    args = parser.parse_args()

    if args.play:
        try:
            play_audio(args.play)
        except AudioPlayerError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"[FATAL] Unexpected error: {e}", file=sys.stderr)
            sys.exit(2)

    if args.read:
        try:
            audio = load_mp3(args.read)
            print(f"Sample rate: {audio.sample_rate} Hz")
            print(f"Samples shape: {audio.samples.shape}")

            total_samples = audio.samples.shape[0]

            if args.range:
                start, end = args.range
                if start < 0 or end > total_samples or start >= end:
                    print(f"[ERROR] Invalid range: {start}–{end}", file=sys.stderr)
                    sys.exit(1)
                print(f"Showing PCM Samples at index {start}:{end}")
                print(audio.samples[start:end])

            else:
                amount = args.amount if args.amount else 20
                mid = total_samples // 2
                start = max(mid - amount // 2, 0)
                end = min(start + amount, total_samples)
                print(f"Showing PCM Samples at index {start}:{end}")
                print(audio.samples[start:end])

        except AudioIOError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
