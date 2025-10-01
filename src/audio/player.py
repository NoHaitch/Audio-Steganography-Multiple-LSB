import threading
import time
from pathlib import Path
from typing import Optional
import librosa
import pygame


class AudioPlayer:
    """Simple audio player using pygame for MP3 files."""

    def __init__(self):
        pygame.mixer.init()
        self.current_file: Optional[str] = None
        self.is_playing = False
        self.is_paused = False
        self.position = 0.0
        self.duration = 0.0
        self._position_thread: Optional[threading.Thread] = None
        self._stop_thread = False

    def load_file(self, file_path: str) -> bool:
        """
        Load an audio file for playback.

        Args:
            file_path: Path to the audio file

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            path_obj = Path(file_path)
            if not path_obj.exists():
                return False

            # Get duration using librosa
            try:
                y, sr = librosa.load(path_obj, sr=None)
                self.duration = len(y) / sr
            except Exception:
                self.duration = 0.0

            # Load with pygame
            pygame.mixer.music.load(file_path)
            self.current_file = file_path
            self.position = 0.0
            return True

        except:
            print(f"Error loading audio file: {file_path}")
            return False

    def play(self) -> bool:
        """Start or resume playback."""
        try:
            if self.current_file is None:
                return False

            if self.is_paused:
                pygame.mixer.music.unpause()
                self.is_paused = False
            else:
                pygame.mixer.music.play()
                self._start_position_tracking()

            self.is_playing = True
            return True

        except:
            print("Error playing audio")
            return False

    def pause(self):
        """Pause playback."""
        if self.is_playing and not self.is_paused:
            pygame.mixer.music.pause()
            self.is_paused = True

    def stop(self):
        """Stop playback and reset position."""
        pygame.mixer.music.stop()
        self.is_playing = False
        self.is_paused = False
        self.position = 0.0
        self._stop_position_tracking()

    def set_volume(self, volume: float):
        """
        Set playback volume.

        Args:
            volume: Volume level (0.0 to 1.0)
        """
        volume = max(0.0, min(1.0, volume))
        pygame.mixer.music.set_volume(volume)

    def get_position(self) -> float:
        """Get current playback position in seconds."""
        return self.position

    def get_duration(self) -> float:
        """Get total duration in seconds."""
        return self.duration

    def is_file_playing(self) -> bool:
        """Check if audio is currently playing."""
        return self.is_playing and pygame.mixer.music.get_busy()

    def _start_position_tracking(self):
        """Start tracking playback position."""
        self._stop_thread = False
        if self._position_thread is None or not self._position_thread.is_alive():
            self._position_thread = threading.Thread(target=self._track_position)
            self._position_thread.daemon = True
            self._position_thread.start()

    def _stop_position_tracking(self):
        """Stop tracking playback position."""
        self._stop_thread = True
        if self._position_thread and self._position_thread.is_alive():
            self._position_thread.join(timeout=1.0)

    def _track_position(self):
        """Track playback position in a separate thread."""
        start_time = time.time()
        start_position = self.position

        while not self._stop_thread and self.is_playing:
            if pygame.mixer.music.get_busy() and not self.is_paused:
                elapsed = time.time() - start_time
                self.position = start_position + elapsed

                # Check if playback finished
                if self.position >= self.duration:
                    self.position = self.duration
                    self.is_playing = False
                    break
            else:
                # Update start time when paused/resumed
                start_time = time.time()
                start_position = self.position

            time.sleep(0.1)  # Update every 100ms

    def cleanup(self):
        """Clean up resources."""
        self.stop()
        pygame.mixer.quit()


# Global audio player instance
audio_player = AudioPlayer()
