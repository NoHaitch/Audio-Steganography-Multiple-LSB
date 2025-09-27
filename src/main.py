import argparse
import sys
from audio import play_audio, load_mp3, calculate_psnr
from audio import AudioPlayerError, AudioIOError
from stego import read_secret_file, StegoInputError


""" List of Args:
  -h, --help                    Show this help message and exit
  -play FILE                    Play an MP3 or WAV file using system default player
  -read FILE                    Read an MP3 file and print decoded PCM samples
    --amount N                      Print N samples (default: 20, from the middle)
    --range START END               Print samples from START to END indices
  -compare ORIGINAL MODIFIED    Compare two MP3 files and calculate the PSNR value.
  -read-secret FILE             Read a secret file and print its metadata and content as bits.
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
        "-compare",
        nargs=2,
        metavar=("ORIGINAL", "MODIFIED"),
        help="Compare two audio files and calculate the PSNR value.",
    )

    parser.add_argument(
        "-read-secret",
        metavar="FILE",
        help="Read a secret file and print its metadata and content as bits.",
    )

    parser.add_argument(
        "--amount",
        type=int,
        help="Number of samples (for -read) or bits (for -read-secret) to print.",
    )

    parser.add_argument(
        "--range",
        nargs=2,
        type=int,
        metavar=("START", "END"),
        help="Range of sample/bit indices to print (overrides --amount).",
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

    if args.compare:
        try:
            original_path, modified_path = args.compare

            print(f"[*] Loading original file: '{original_path}'")
            original_audio = load_mp3(original_path)

            print(f"[*] Loading modified file: '{modified_path}'")
            modified_audio = load_mp3(modified_path)

            min_len = min(len(original_audio.samples), len(modified_audio.samples))
            original_samples = original_audio.samples[:min_len]
            modified_samples = modified_audio.samples[:min_len]

            print("[*] Calculating PSNR...")
            psnr = calculate_psnr(original_samples, modified_samples)

            print("\n" + "---" * 10)
            print("   Comparison Complete")
            print(f"   PSNR Value: {psnr:.2f} dB")
            print("---" * 10)

        except AudioIOError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"[FATAL] Unexpected error: {e}", file=sys.stderr)
            sys.exit(2)

    if args.read_secret:
        try:
            secret_data = read_secret_file(args.read_secret)
            
            print(f"File Path: {args.read_secret}")
            print(f"File Size: {secret_data.size_in_bytes} bytes")
            print(f"File Extension: '{secret_data.extension}'")

            bit_string = "".join(format(byte, '08b') for byte in secret_data.content)
            total_bits = len(bit_string)
            print(f"Total Bits: {total_bits}")
            
            if args.range:
                start, end = args.range
                if start < 0 or end > total_bits or start >= end:
                    print(f"[ERROR] Invalid bit range: {start}–{end}", file=sys.stderr)
                    sys.exit(1)
                print(f"\nShowing bits from index {start} to {end}:")
                print(bit_string[start:end])
            else:
                amount = args.amount if args.amount else 80
                end = min(amount, total_bits)
                print(f"\nShowing first {end} bits:")
                print(bit_string[:end])

        except StegoInputError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"[FATAL] Unexpected error: {e}", file=sys.stderr)
            sys.exit(2)


if __name__ == "__main__":
    main()

