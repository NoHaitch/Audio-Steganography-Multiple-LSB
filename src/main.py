import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MP3 Steganography with Multiple LSB, Seed, and Optional Cipher",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed for pseudo-random embedding location (stego key).",
    )

    parser.add_argument(
        "--cipher",
        action="store_true",
        help="Use Vigenere cipher for the secret message.",
    )

    parser.add_argument(
        "--key",
        type=str,
        default=None,
        help="Key for Vigenere cipher (required if --cipher is set).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- Embed ---
    embed_parser = subparsers.add_parser(
        "embed", help="Embed a secret message into a cover MP3."
    )
    embed_parser.add_argument(
        "-c", "--cover",
        type=Path,
        required=True,
        help="Path to the cover MP3 file."
    )
    embed_parser.add_argument(
        "-s", "--secret",
        type=Path,
        required=True,
        help="Path to the secret message file."
    )
    embed_parser.add_argument(
        "-n", "--lsb-count",
        type=int,
        choices=[1, 2, 3, 4],
        required=True,
        help="Number of LSBs to use for embedding (1–4)."
    )
    embed_parser.add_argument(
        "-o", "--output",
        type=Path,
        required=True,
        help="Path to save the stego MP3 file."
    )

    # --- Extract ---
    extract_parser = subparsers.add_parser(
        "extract", help="Extract a hidden secret message from a stego MP3."
    )
    extract_parser.add_argument(
        "-i", "--input",
        type=Path,
        required=True,
        help="Path to the stego MP3 file."
    )
    extract_parser.add_argument(
        "-o", "--output",
        type=Path,
        required=True,
        help="Path or folder to save the extracted secret message."
    )

    # --- Compare ---
    compare_parser = subparsers.add_parser(
        "compare", help="Compare original and stego MP3 using PSNR."
    )
    compare_parser.add_argument(
        "-a", "--original",
        type=Path,
        required=True,
        help="Path to the original MP3 file."
    )
    compare_parser.add_argument(
        "-b", "--modified",
        type=Path,
        required=True,
        help="Path to the stego or modified MP3 file."
    )

    args = parser.parse_args()

    if args.command == "embed":
        # TODO: implement embedding workflow
        # - read cover
        # - read secret
        # - maybe encrypt with Vigenere
        # - embed with LSB
        # - save to output
        # - print PSNR, result path, #bits embedded, seed used
        pass

    elif args.command == "extract":
        # TODO: implement extraction workflow
        # - read stego
        # - extract bits (with seed if given)
        # - maybe decrypt with Vigenere
        # - save result file
        # - print location, size, failure info if missing signatures
        pass

    elif args.command == "compare":
        # TODO: implement comparison workflow
        # - load both MP3s
        # - decode PCM
        # - compute PSNR
        # - print result
        pass

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
