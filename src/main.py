import argparse
import sys
from pathlib import Path
import flet as ft
from stego import compare_mp3_files, embed, extract
from gui import run_gui


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MP3 Steganography with Multiple LSB, Seed, and Optional Cipher",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # GUI
    gui_parser = subparsers.add_parser(
        "gui", help="Run program in GUI"
    )

    # ----- Embed -----
    embed_parser = subparsers.add_parser(
        "embed", help="Embed a secret message into a cover MP3."
    )
    embed_parser.add_argument(
        "-c", "--cover", type=Path, required=True, help="Path to the cover MP3 file."
    )
    embed_parser.add_argument(
        "-s",
        "--secret",
        type=Path,
        required=True,
        help="Path to the secret message file.",
    )
    embed_parser.add_argument(
        "-n",
        "--lsb-count",
        type=int,
        choices=[1, 2, 3, 4],
        required=True,
        help="Number of LSBs to use for embedding (1-4).",
    )
    embed_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Path to save the stego MP3 file.",
    )
    embed_parser.add_argument(
        "--random",
        action="store_true",
        help="Use randomized starting position for embedding (requires --key).",
    )
    embed_parser.add_argument(
        "--cipher",
        action="store_true",
        help="Encrypt the embedded file using Vigenere cipher"
    )
    embed_parser.add_argument(
        "--key",
        type=str,
        help="Key for randomizing start position and/or cipher"
    )

    # ----- Extract -----
    extract_parser = subparsers.add_parser(
        "extract", help="Extract a hidden secret message from a stego MP3."
    )
    extract_parser.add_argument(
        "-i", "--input", type=Path, required=True, help="Path to the stego MP3 file."
    )
    extract_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Path or folder to save the extracted secret message.",
    )
    extract_parser.add_argument(
        "--random",
        action="store_true",
        help="Use randomized starting position for extraction (requires --key).",
    )
    extract_parser.add_argument(
        "--key",
        type=str,
        help="Key for randomizing start position and/or cipher"
    )
    extract_parser.add_argument(
        "--cipher",
        action="store_true",
        help="Encrypt the embedded file using Vigenere cipher"
    )

    # ----- Compare -----
    compare_parser = subparsers.add_parser(
        "compare", help="Compare original and stego MP3 using PSNR."
    )
    compare_parser.add_argument(
        "-a",
        "--original",
        type=Path,
        required=True,
        help="Path to the original MP3 file.",
    )
    compare_parser.add_argument(
        "-b",
        "--modified",
        type=Path,
        required=True,
        help="Path to the stego or modified MP3 file.",
    )

    args = parser.parse_args()

    # Validation for random option
    if hasattr(args, "random") and args.random and not args.key:
        print("Error: --random option requires --key to be provided.", file=sys.stderr)
        sys.exit(1)

    if args.command == "embed":
        embed(
            args.cover,
            args.secret,
            args.output,
            args.lsb_count,
            encrypt=args.cipher,
            key=args.key,
            random_position=getattr(args, "random", False),
        )

    elif args.command == "extract":
        extract(
            args.input,
            args.output,
            encrypted=args.cipher,
            key=args.key,
            random_position=getattr(args, "random", False),
        )

    elif args.command == "compare":
        try:
            psnr_value = compare_mp3_files(args.original, args.modified)

            print("\n" + "---" * 10)
            print("    Comparison Complete")
            print(f"     Original: {args.original}")
            print(f"     Modified: {args.modified}")
            print(f"     PSNR Value: {psnr_value:.4f} dB")
            print("---" * 10)

        except Exception as e:
            exc_type = type(e).__name__
            print(f"[{exc_type}] Failed to compare: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "gui":
        try:
            print("Starting Audio Steganography GUI\n")

            ft.app(target=run_gui)

        except ImportError as e:
            print(f"Import error: {e}")
            sys.exit(1)

        except Exception as e:
            print(f"Error starting GUI: {e}")
            sys.exit(1)




    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
