# Audio-Steganography-Multiple-LSB

A Python implementation of audio steganography using multiple Least Significant Bits (LSB) technique. This program allows you to hide secret messages or files within MP3 audio files while maintaining audio quality.

## Features

- **Multiple LSB Embedding**: Support for 1-4 LSBs for variable capacity
- **Encryption Support**: Vigenère cipher encryption for enhanced security
- **Randomized Positioning**: Randomize starting position for embedding
- **Quality Measurement**: PSNR (Peak Signal-to-Noise Ratio) calculation for audio quality assessment
- **GUI Interface**: User-friendly graphical interface using Flet
- **File Format Support**: Works with various file types for secret messages

## Project Structure

```text
src/
├── main.py              # Main entry point with CLI interface
├── audio/               # Audio file operations and playback
├── cipher/              # Encryption algorithms (Vigenère cipher)
├── fileio/              # File input/output operations
├── gui/                 # Graphical user interface
├── randomizer/          # Position randomization utilities
├── stego/               # Core steganography algorithms and PSNR calculation
└── utils/               # Shared types and exception handling
```

## Requirements

### Core Dependencies

- `librosa` - Audio analysis and processing
- `soundfile` - Audio file I/O
- `numpy` - Numerical computations
- `flet` - GUI framework
- `pydub` - Audio manipulation

## Installation

1. **Clone the repository:**

   ```bash
   git clone <repository-url>
   cd Audio-Steganography-Multiple-LSB
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

## Usage

The program can be used in two modes: GUI and command-line interface

### GUI Mode

Launch the graphical interface:

```bash
python src/main.py gui
```

### Command Line Interface

#### 1. Embed a Secret Message

```bash
python src/main.py embed \
  --cover path/to/cover.mp3 \
  --secret path/to/secret.txt \
  --output path/to/output.mp3 \
  --lsb-count 2 \
  [--random] \
  [--cipher] \
  [--key "your-key"]
```

**Parameters:**

- `--cover`: Path to the cover MP3 file
- `--secret`: Path to the secret message/file
- `--output`: Path for the output steganographic MP3
- `--lsb-count`: Number of LSBs to use (1-4, higher = more capacity, lower quality)
- `--random`: Use randomized starting position (requires `--key`)
- `--cipher`: Encrypt the secret using Vigenère cipher (requires `--key`)
- `--key`: Key for randomization and/or encryption

#### 2. Extract a Hidden Message

```bash
python src/main.py extract \
  --input path/to/stego.mp3 \
  --output path/to/extracted/ \
  [--random] \
  [--cipher] \
  [--key "your-key"]
```

**Parameters:**

- `--input`: Path to the steganographic MP3 file
- `--output`: Path/folder to save the extracted message
- `--random`: Use randomized position (must match embedding settings)
- `--cipher`: Decrypt using Vigenère cipher (must match embedding settings)
- `--key`: Key for randomization and/or decryption (must match embedding key)

#### 3. Compare Audio Quality (PSNR)

```bash
python src/main.py compare \
  --original path/to/original.mp3 \
  --modified path/to/stego.mp3
```

**Parameters:**

- `--original`: Path to the original MP3 file
- `--modified`: Path to the modified/steganographic MP3 file
