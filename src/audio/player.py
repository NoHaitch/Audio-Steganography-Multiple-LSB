import threading
import time
from pathlib import Path
from typing import Optional

try:
    import pyaudio

    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False

try:
    from pydub import AudioSegment

    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False


class PythonAudioPlayer:
    """Audio player using Python libraries (pydub + pyaudio)."""

    def __init__(self):
        self.current_file: Optional[str] = None
        self.audio_segment: Optional[AudioSegment] = None
        self.is_playing = False
        self.is_paused = False
        self.position = 0.0  # Current position in seconds
        self.duration = 0.0  # Total duration in seconds
        self.volume = 0.5  # Volume (0.0 to 1.0)

        # Playback thread management
        self._playback_thread: Optional[threading.Thread] = None
        self._stop_playback = False
        self._pause_event = threading.Event()
        self._pause_event.set()  # Start unpaused

        # PyAudio setup
        self.pyaudio_instance = None
        self.stream = None

        if PYAUDIO_AVAILABLE:
            self.pyaudio_instance = pyaudio.PyAudio()

    def load_file(self, file_path: str) -> bool:
        """
        Load an audio file for playback.

        Args:
            file_path: Path to the audio file

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not PYDUB_AVAILABLE:
                print(
                    "Error: pydub not available. Please install with: pip install pydub"
                )
                return False

            path_obj = Path(file_path)
            if not path_obj.exists():
                print(f"Error: File does not exist: {file_path}")
                return False

            # Stop current playback
            self.stop()

            # Load audio file
            self.audio_segment = AudioSegment.from_file(file_path)
            self.current_file = file_path
            self.duration = len(self.audio_segment) / 1000.0  # Convert ms to seconds
            self.position = 0.0

            print(f"Loaded audio file: {file_path}")
            print(f"Duration: {self.duration:.2f} seconds")
            return True

        except Exception as e:
            print(f"Error loading audio file {file_path}: {e}")
            return False

    def play(self) -> bool:
        """Start or resume playback."""
        if not self.audio_segment:
            print("No audio file loaded")
            return False

        try:
            if self.is_paused:
                # Resume playback
                self._pause_event.set()
                self.is_paused = False
                print("Resumed playback")
                return True

            if self.is_playing:
                return True

            # Start new playback
            self.is_playing = True
            self._stop_playback = False
            self._pause_event.set()

            self._playback_thread = threading.Thread(target=self._playback_worker)
            self._playback_thread.daemon = True
            self._playback_thread.start()

            print("Started playback")
            return True

        except Exception as e:
            print(f"Error starting playback: {e}")
            return False

    def pause(self):
        """Pause playback."""
        if self.is_playing and not self.is_paused:
            self._pause_event.clear()
            self.is_paused = True
            print("Paused playback")

    def stop(self):
        """Stop playback and reset position."""
        self._stop_playback = True
        self._pause_event.set()  # Unblock if paused

        if self._playback_thread and self._playback_thread.is_alive():
            self._playback_thread.join(timeout=1.0)

        self.is_playing = False
        self.is_paused = False
        self.position = 0.0
        print("Stopped playback")

    def seek(self, position: float):
        """
        Seek to a specific position in the audio.

        Args:
            position: Position in seconds
        """
        if self.audio_segment:
            self.position = max(0.0, min(position, self.duration))
            print(f"Seeked to position: {self.position:.2f}s")

    def set_volume(self, volume: float):
        """
        Set playback volume.

        Args:
            volume: Volume level (0.0 to 1.0)
        """
        self.volume = max(0.0, min(1.0, volume))
        print(f"Volume set to: {self.volume:.2f}")

    def get_position(self) -> float:
        """Get current playback position in seconds."""
        return self.position

    def get_duration(self) -> float:
        """Get total duration in seconds."""
        return self.duration

    def is_file_playing(self) -> bool:
        """Check if audio is currently playing."""
        return self.is_playing and not self.is_paused

    def _playback_worker(self):
        """Worker method for audio playback in a separate thread."""
        if not self.audio_segment or not PYAUDIO_AVAILABLE:
            self.is_playing = False
            return

        try:
            # Apply volume
            audio_data = self.audio_segment
            if self.volume != 1.0:
                # Convert volume from 0-1 to dB (roughly -60dB to 0dB)
                db_change = (self.volume - 1.0) * 60
                audio_data = audio_data + db_change

            # Start from current position
            start_ms = int(self.position * 1000)
            audio_data = audio_data[start_ms:]

            # Setup pyaudio stream
            chunk_size = 1024
            format_map = {
                1: pyaudio.paInt8,
                2: pyaudio.paInt16,
                4: pyaudio.paInt32,
            }

            format = format_map.get(audio_data.sample_width, pyaudio.paInt16)

            self.stream = self.pyaudio_instance.open(
                format=format,
                channels=audio_data.channels,
                rate=audio_data.frame_rate,
                output=True,
                frames_per_buffer=chunk_size,
            )

            # Convert to raw audio data
            raw_data = audio_data.raw_data

            # Playback loop
            bytes_per_second = (
                audio_data.frame_rate * audio_data.channels * audio_data.sample_width
            )
            start_time = time.time()
            bytes_played = 0

            for i in range(0, len(raw_data), chunk_size):
                if self._stop_playback:
                    break

                # Wait if paused
                self._pause_event.wait()

                if self._stop_playback:
                    break

                # Play chunk
                chunk = raw_data[i : i + chunk_size]
                self.stream.write(chunk)
                bytes_played += len(chunk)

                # Update position
                if not self.is_paused:
                    self.position = start_ms / 1000.0 + (
                        bytes_played / bytes_per_second
                    )

                # Check if we've reached the end
                if self.position >= self.duration:
                    break

            # Cleanup
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None

            # If we finished normally, stop
            if not self._stop_playback:
                self.position = self.duration
                self.is_playing = False
                print("Playback finished")

        except Exception as e:
            print(f"Error during playback: {e}")
        finally:
            self.is_playing = False
            if self.stream:
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                except:
                    pass
                self.stream = None

    def cleanup(self):
        """Clean up resources."""
        self.stop()
        if self.pyaudio_instance:
            self.pyaudio_instance.terminate()
            self.pyaudio_instance = None
        print("Audio player cleaned up")


# Global audio player instance
audio_player = PythonAudioPlayer()
