# Audio-Steganography-Multiple-LSB

## requirements

librosa soundfile numpy  
dev: mypy

### commands:

```shell
pip freeze > requirements.txt
pip install -r requirements.txt
```

3. Compare MP3 using PSNR

```python
python main.py compare --original ..\AWIKWOK\test\original.mp3 --modified ..\AWIKWOK\test\result.mp3
```
