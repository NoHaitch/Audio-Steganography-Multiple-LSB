<!-- Back to Top Link-->

<a name="readme-top"></a>

<br />
<div align="center">
  <h1 align="center">Audio Steganography Multiple LSB</h1>

  <p align="center">
    <h4>Embedding Secret Messages to MP3 Audio File using M-LSB Method.</h4>
  </p>
</div>

<div align="center" id="contributor">
  <strong>
    <h3>Made By:</h3>
    <table align="center">
      <tr>
        <td>NIM</td>
        <td>Name</td>
      </tr>
      <tr>
        <td>13522071</td>
        <td>Bagas Sambega Rosyada

</td>
      </tr>
      <tr>
        <td>13522091</td>
        <td>Raden Francisco Trianto B.</td>
      </tr>
    </table>
  </strong>
  <br>
</div>

## About The Project

Embedding Secret Messages to MP3 Audio File using M-LSB Method.

For Course IF4020 Cryptography, we made a program to do Steganography in MP3 using Multiple LSB(Least Significant Byte) Method. Embedding using MP3 has many challenge, mainly due to how MP3 itself works. MP3 is a low quality, lossy compression, this mean that the the proses of converting audio to MP3 will loss data and its ireversable. We handle the problem by purely treating the MP3 as a bitstream and modify the LSB with percision. This method however, is limited to only change the Audio Data inside the Frames of MP3. The ID3 tag is optional so we can't depend on it, while the Frame Header cannot be change or the file will be corrupted. We also implemented additional Vigenere Cipher for security and Seed for choosing the starting embed location.

The program iself can be run in 2 modes: pure CLI or using the GUI.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Getting Started

### Prerequisites

Project dependencies:

- Python 3.13

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Installation

1. Clone the repo
   ```sh
   git clone https://github.com/NoHaitch/Audio-Steganography-Multiple-LSB
   ```
2. Open Cloned Directory
   ```
   cd Audio-Steganography-Multiple-LSB
   ```
3. Install Python Dependencies
   ```sh
   pip install -r requirement.txt
   ```
4. Run The GUI
   ```sh
   python src/main.py gui
   ```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

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


<p align="right">(<a href="#readme-top">back to top</a>)</p>
