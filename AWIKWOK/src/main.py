import argparse
import sys
import os

from audio import play_audio, load_mp3, save_mp3, calculate_psnr
from audio import AudioPlayerError, AudioIOError

from stego import read_secret_file, embed, AudioSteganography
from stego import StegoInputError, StegoEmbbedError


# List of Args:
#   -h, --help                    Show this help message and exit
#   -play FILE                    Play an MP3 or WAV file.
#   -read FILE                    Read an MP3 and print PCM samples.
#     --amount N                  Print N samples/bits.
#     --range START END           Print samples/bits in a range.
#   -compare ORIGINAL MODIFIED    Compare two MP3 files using PSNR.
#   -read-secret FILE             Read a secret file and print its content as bits.
#   -test-recompression FILE      Load, save, and compare an MP3 to test quality loss.
#   -embed COVER SECRET LSB       Embed a secret file into a cover MP3.
#     --output FILE               Specify the output path for the stego audio.
#   -hide COVER SECRET OUTPUT     Hide a file in audio using AudioSteganography class.
#     --bits-per-sample N         Number of LSB bits to use (1-4, default: 2).
#   -extract STEGO_AUDIO          Extract hidden file from steganographic audio.
#     --extract-output DIR        Directory to save the extracted file.


def _bytes_to_bit_string(data: bytes) -> str:
    """Convert bytes to a string of '0's and '1's."""
    return "".join(format(byte, "08b") for byte in data)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MP3 Steganography using Multiple LSB",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "-play",
        metavar="FILE",
        type=os.path.abspath,
        help="Play an MP3 or WAV file.",
    )

    parser.add_argument(
        "-read",
        metavar="FILE",
        type=os.path.abspath,
        help="Read an MP3 file and print decoded PCM samples.",
    )

    parser.add_argument(
        "-compare",
        nargs=2,
        metavar=("ORIGINAL", "MODIFIED"),
        type=os.path.abspath,
        help="Compare two audio files and calculate the PSNR value.",
    )

    parser.add_argument(
        "-read-secret",
        metavar="FILE",
        type=os.path.abspath,
        help="Read a secret file and print its metadata and content as bits.",
    )

    parser.add_argument(
        "-test-recompression",
        metavar="FILE",
        type=os.path.abspath,
        help="Load, save, and then compare an MP3 to test recompression quality loss.",
    )

    parser.add_argument(
        "-embed",
        nargs=3,
        metavar=("COVER_MP3", "SECRET_FILE", "LSB_COUNT"),
        help="Embed a secret file into a cover MP3 using n LSBs.",
    )

    parser.add_argument(
        "-hide",
        nargs=3,
        metavar=("COVER_AUDIO", "SECRET_FILE", "OUTPUT_AUDIO"),
        help="Hide a file in audio using AudioSteganography class.",
    )

    parser.add_argument(
        "-extract",
        metavar="STEGO_AUDIO",
        type=os.path.abspath,
        help="Extract hidden file from steganographic audio.",
    )

    parser.add_argument(
        "--output",
        metavar="FILE",
        type=os.path.abspath,
        help="Specify the output path for the generated stego audio file.",
    )

    parser.add_argument(
        "--bits-per-sample",
        type=int,
        default=2,
        choices=[1, 2, 3, 4],
        help="Number of LSB bits to use for hiding data (1-4, default: 2).",
    )

    parser.add_argument(
        "--extract-output",
        metavar="DIR",
        type=os.path.abspath,
        default=".",
        help="Directory to save the extracted file (default: current directory).",
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
            print(f"File: {args.read}")
            print(f"Sample rate: {audio.sample_rate} Hz")
            print(f"Samples shape: {audio.samples.shape}")

            total_samples = audio.samples.shape[0]
            if args.range:
                start, end = args.range
                if not (0 <= start < end <= total_samples):
                    print(
                        f"[ERROR] Invalid sample range: {start}-{end}", file=sys.stderr
                    )
                    sys.exit(1)
                print(f"\nShowing PCM Samples from index {start} to {end}:")
                print(audio.samples[start:end])
            else:
                amount = args.amount if args.amount else 20
                mid = total_samples // 2
                start = max(mid - amount // 2, 0)
                end = min(start + amount, total_samples)
                print(
                    f"\nShowing {end-start} PCM Samples from the middle (index {start}-{end}):"
                )
                print(audio.samples[start:end])
        except AudioIOError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)

    if args.compare:
        try:
            original_path, modified_path = args.compare
            print(
                f"[*] Comparing:\n  - Original: {original_path}\n  - Modified: {modified_path}"
            )

            original_audio = load_mp3(original_path)
            modified_audio = load_mp3(modified_path)

            min_len = min(len(original_audio.samples), len(modified_audio.samples))
            psnr = calculate_psnr(
                original_audio.samples[:min_len], modified_audio.samples[:min_len]
            )

            print("\n" + "---" * 10)
            print("    Comparison Complete")
            print(f"     PSNR Value (File-to-File): {psnr:.2f} dB")
            print("---" * 10)
        except AudioIOError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)

    if args.read_secret:
        try:
            secret_data = read_secret_file(args.read_secret)
            print(f"File Path: {args.read_secret}")
            print(f"File Size: {secret_data.size_in_bytes} bytes")
            print(f"File Extension: '{secret_data.extension}'")

            bit_string = _bytes_to_bit_string(secret_data.content)
            total_bits = len(bit_string)
            print(f"Total Bits: {total_bits}")

            if args.range:
                start, end = args.range
                if not (0 <= start < end <= total_bits):
                    print(f"[ERROR] Invalid bit range: {start}-{end}", file=sys.stderr)
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

    if args.test_recompression:
        try:
            original_path = args.test_recompression
            print(f"[*] Testing recompression for: '{original_path}'")

            print("    -> Loading original file...")
            original_audio = load_mp3(original_path)

            recompressed_path = os.path.join(
                os.path.dirname(original_path), "recompressed_test.mp3"
            )
            print(f"    -> Saving to '{recompressed_path}'...")
            save_mp3(recompressed_path, original_audio)

            print("    -> Loading recompressed file for comparison...")
            recompressed_audio = load_mp3(recompressed_path)

            print("    -> Calculating PSNR...")
            min_len = min(len(original_audio.samples), len(recompressed_audio.samples))
            psnr = calculate_psnr(
                original_audio.samples[:min_len], recompressed_audio.samples[:min_len]
            )

            print("\n" + "---" * 10)
            print("    Recompression Test Complete")
            print(f"     PSNR between original and recompressed file: {psnr:.2f} dB")
            print("---" * 10)
        except (AudioIOError, StegoEmbbedError) as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)

    if args.embed:
        try:
            cover_path_rel, secret_path_rel, n_lsb_str = args.embed
            cover_path = os.path.abspath(cover_path_rel)
            secret_path = os.path.abspath(secret_path_rel)
            n_lsb = int(n_lsb_str)

            print(f"[*] Loading cover audio: '{cover_path}'")
            cover_audio = load_mp3(cover_path)

            print(f"[*] Loading secret file: '{secret_path}'")
            secret_data_obj = read_secret_file(secret_path)

            print(f"[*] Encoding payload using {n_lsb}-LSB method...")
            stego_audio_data = embed(cover_audio, secret_data_obj.content, n_lsb)

            print("[*] Calculating in-memory PSNR (Original PCM vs. Stego PCM)...")
            psnr_in_memory = calculate_psnr(
                cover_audio.samples, stego_audio_data.samples
            )

            output_path = args.output if args.output else "stego_output.mp3"
            print(f"[*] Saving stego audio to '{output_path}'...")
            save_mp3(output_path, stego_audio_data)

            print("\n" + "---" * 10)
            print("    Encoding successful!")
            print(f"     Stego file saved to: {output_path}")
            print(f"     PSNR (In-Memory LSB change): {psnr_in_memory:.2f} dB")
            print("---" * 10)
            print("\n[INFO] To check the final quality loss from re-encoding,")
            print(f'       run: python main.py -compare "{cover_path}" "{output_path}"')

        except (AudioIOError, StegoInputError, StegoEmbbedError, ValueError) as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"[FATAL] An unexpected error occurred: {e}", file=sys.stderr)
            sys.exit(2)

    if args.hide:
        try:
            cover_path_rel, secret_path_rel, output_path_rel = args.hide
            cover_path = os.path.abspath(cover_path_rel)
            secret_path = os.path.abspath(secret_path_rel)
            output_path = os.path.abspath(output_path_rel)

            # Validate input files
            if not os.path.exists(cover_path):
                print(
                    f"[ERROR] Cover audio file not found: {cover_path}", file=sys.stderr
                )
                sys.exit(1)

            if not os.path.exists(secret_path):
                print(f"[ERROR] Secret file not found: {secret_path}", file=sys.stderr)
                sys.exit(1)

            bits_per_sample = args.bits_per_sample
            print(
                f"[*] Using AudioSteganography with {bits_per_sample}-bit LSB embedding"
            )

            steganography = AudioSteganography(bits_per_sample=bits_per_sample)
            steganography.hide_file(cover_path, secret_path, output_path)

        except Exception as e:
            print(f"[ERROR] Failed to hide file: {e}", file=sys.stderr)
            sys.exit(1)

    if args.extract:
        try:
            stego_audio_path = args.extract
            output_dir = args.extract_output

            if not os.path.exists(stego_audio_path):
                print(
                    f"[ERROR] Steganographic audio file not found: {stego_audio_path}",
                    file=sys.stderr,
                )
                sys.exit(1)

            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                print(f"[*] Created output directory: {output_dir}")

            # Try different bit configurations if extraction fails
            bits_per_sample = (
                args.bits_per_sample if hasattr(args, "bits_per_sample") else None
            )

            if bits_per_sample:
                # Use specified bits per sample
                print(f"[*] Attempting extraction with {bits_per_sample}-bit LSB...")
                steganography = AudioSteganography(bits_per_sample=bits_per_sample)
                extracted_file = steganography.extract_file(
                    stego_audio_path, output_dir
                )
                print(f"[*] Extraction successful! File saved to: {extracted_file}")
            else:
                # Try different configurations
                success = False
                for bits in [2, 1, 3, 4]:  # Try most common first
                    try:
                        print(f"[*] Attempting extraction with {bits}-bit LSB...")
                        steganography = AudioSteganography(bits_per_sample=bits)
                        extracted_file = steganography.extract_file(
                            stego_audio_path, output_dir
                        )
                        print(
                            f"[*] Extraction successful with {bits}-bit LSB! File saved to: {extracted_file}"
                        )
                        success = True
                        break
                    except Exception as e:
                        if bits == 4:  # Last attempt
                            print(
                                f"[ERROR] All extraction attempts failed. Last error: {e}",
                                file=sys.stderr,
                            )
                        continue

                if not success:
                    sys.exit(1)

        except Exception as e:
            print(f"[ERROR] Failed to extract file: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
