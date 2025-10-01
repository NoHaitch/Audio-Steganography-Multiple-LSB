import os
import threading
from pathlib import Path
from typing import Optional

import flet as ft

from stego import embed, extract, compare_mp3_files
from audio.player import audio_player


class GUI:
    """
    GUI implementation for LSB-embedding program in MP3 files
    """

    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Audio Steganography - Multiple LSB"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.window.width = 900
        self.page.window.height = 700
        self.page.window.resizable = True

        # File paths
        self.cover_audio_path = ""
        self.secret_file_path = ""
        self.stego_audio_path = ""
        self.output_audio_path = ""
        self.extract_output_folder = ""
        self.compare_original_path = ""
        self.compare_modified_path = ""

        # UI elements
        self.status_text = ft.Text("Ready", size=14, color="green")
        self.progress_bar = ft.ProgressBar(visible=False)

        # Initialize UI
        self.setup_ui()

    def show_notification(self, message: str, color: str = "green"):
        """Show a notification message to the user."""
        snack_bar = ft.SnackBar(
            content=ft.Text(message, color="white"),
            bgcolor=color,
            duration=3000,  # 3 seconds
        )
        self.page.overlay.append(snack_bar)
        self.page.update()
        snack_bar.open = True
        self.page.update()

    def setup_ui(self):
        """Setup UI"""

        # Main tabs
        tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(text="Embed", content=self.create_embed_tab()),
                ft.Tab(text="Extract", content=self.create_extract_tab()),
                ft.Tab(text="Compare", content=self.create_compare_tab()),
                ft.Tab(text="Audio Player", content=self.create_player_tab()),
            ],
        )

        # Main layout
        self.page.add(
            ft.Column(
                [
                    ft.Container(
                        content=ft.Text(
                            "Audio Steganography - Multiple LSB",
                            size=24,
                            weight=ft.FontWeight.BOLD,
                            color="blue",
                        ),
                        padding=ft.padding.all(10),
                        alignment=ft.alignment.center,
                    ),
                    ft.Divider(),
                    tabs,
                    ft.Divider(),
                    ft.Container(
                        content=ft.Column([self.status_text, self.progress_bar]),
                        padding=ft.padding.all(10),
                    ),
                ]
            )
        )

    def create_embed_tab(self):
        """Tab embed"""

        # File selection controls
        self.cover_audio_text = ft.Text("No file selected", size=12)
        self.secret_file_text = ft.Text("No file selected", size=12)
        self.output_audio_text = ft.Text("No file selected", size=12)

        self.lsb_count_dropdown = ft.Dropdown(
            label="LSB Count",
            value="2",
            options=[
                ft.dropdown.Option("1", "1 bit"),
                ft.dropdown.Option("2", "2 bits"),
                ft.dropdown.Option("3", "3 bits"),
                ft.dropdown.Option("4", "4 bits"),
            ],
            width=150,
        )

        self.encrypt_checkbox = ft.Checkbox(
            label="Enable Encryption (Vigenère Cipher)",
            value=False,
            on_change=self.on_encrypt_change,
        )

        self.random_position_checkbox = ft.Checkbox(
            label="Use Random Starting Position",
            value=False,
            on_change=self.on_random_change,
        )

        self.key_textfield = ft.TextField(
            label="Encryption/Random Key",
            password=True,
            can_reveal_password=True,
            disabled=True,
            width=300,
        )

        return ft.Container(
            content=ft.Column(
                [
                    # File selection section
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text(
                                    "File Selection", size=18, weight=ft.FontWeight.BOLD
                                ),
                                ft.Row(
                                    [
                                        ft.ElevatedButton(
                                            "Select Cover Audio (MP3)",
                                            on_click=self.select_cover_audio,
                                        ),
                                        ft.Container(
                                            self.cover_audio_text, expand=True
                                        ),
                                    ]
                                ),
                                ft.Row(
                                    [
                                        ft.ElevatedButton(
                                            "Select Secret File",
                                            on_click=self.select_secret_file,
                                        ),
                                        ft.Container(
                                            self.secret_file_text, expand=True
                                        ),
                                    ]
                                ),
                                ft.Row(
                                    [
                                        ft.ElevatedButton(
                                            "Select Output Location",
                                            on_click=self.select_output_audio,
                                        ),
                                        ft.Container(
                                            self.output_audio_text, expand=True
                                        ),
                                    ]
                                ),
                            ]
                        ),
                        padding=ft.padding.all(10),
                        border=ft.border.all(1, "grey"),
                        border_radius=5,
                    ),
                    # Settings section
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text("Settings", size=18, weight=ft.FontWeight.BOLD),
                                ft.Row(
                                    [
                                        self.lsb_count_dropdown,
                                        ft.Container(width=20),
                                        self.encrypt_checkbox,
                                    ]
                                ),
                                ft.Row(
                                    [
                                        self.random_position_checkbox,
                                    ]
                                ),
                                ft.Row(
                                    [
                                        self.key_textfield,
                                    ]
                                ),
                            ]
                        ),
                        padding=ft.padding.all(10),
                        border=ft.border.all(1, "grey"),
                        border_radius=5,
                    ),
                    # Action button
                    ft.Container(
                        content=ft.ElevatedButton(
                            "Embed Secret File",
                            color="white",
                            bgcolor="blue",
                            on_click=self.perform_embed,
                        ),
                        alignment=ft.alignment.center,
                        padding=ft.padding.all(10),
                    ),
                ]
            ),
            padding=ft.padding.all(10),
        )

    def create_extract_tab(self):
        """Tab extract"""

        # File selection
        self.stego_audio_text = ft.Text("No file selected", size=12)
        self.extract_output_text = ft.Text("No folder selected", size=12)

        # Settings
        self.extract_encrypt_checkbox = ft.Checkbox(
            label="Payload is Encrypted",
            value=False,
            on_change=self.on_extract_encrypt_change,
        )

        self.extract_random_checkbox = ft.Checkbox(
            label="Used Random Starting Position",
            value=False,
            on_change=self.on_extract_random_change,
        )

        self.extract_key_textfield = ft.TextField(
            label="Decryption/Random Key",
            password=True,
            can_reveal_password=True,
            disabled=True,
            width=300,
        )

        return ft.Container(
            content=ft.Column(
                [
                    # File selection section
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text(
                                    "File Selection", size=18, weight=ft.FontWeight.BOLD
                                ),
                                ft.Row(
                                    [
                                        ft.ElevatedButton(
                                            "Select Stego Audio (MP3)",
                                            on_click=self.select_stego_audio,
                                        ),
                                        ft.Container(
                                            self.stego_audio_text, expand=True
                                        ),
                                    ]
                                ),
                                ft.Row(
                                    [
                                        ft.ElevatedButton(
                                            "Select Output Folder",
                                            on_click=self.select_extract_output,
                                        ),
                                        ft.Container(
                                            self.extract_output_text, expand=True
                                        ),
                                    ]
                                ),
                            ]
                        ),
                        padding=ft.padding.all(10),
                        border=ft.border.all(1, "grey"),
                        border_radius=5,
                    ),
                    # Settings section
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text("Settings", size=18, weight=ft.FontWeight.BOLD),
                                ft.Row(
                                    [
                                        self.extract_encrypt_checkbox,
                                    ]
                                ),
                                ft.Row(
                                    [
                                        self.extract_random_checkbox,
                                    ]
                                ),
                                ft.Row(
                                    [
                                        self.extract_key_textfield,
                                    ]
                                ),
                            ]
                        ),
                        padding=ft.padding.all(10),
                        border=ft.border.all(1, "grey"),
                        border_radius=5,
                    ),
                    # Action button
                    ft.Container(
                        content=ft.ElevatedButton(
                            "Extract Secret File",
                            color="white",
                            bgcolor="green",
                            on_click=self.perform_extract,
                        ),
                        alignment=ft.alignment.center,
                        padding=ft.padding.all(10),
                    ),
                ]
            ),
            padding=ft.padding.all(10),
        )

    def create_compare_tab(self):
        """Tab compare"""

        # File selection controls
        self.compare_original_text = ft.Text("No file selected", size=12)
        self.compare_modified_text = ft.Text("No file selected", size=12)

        # Results display
        self.psnr_result_text = ft.Text("", size=16, weight=ft.FontWeight.BOLD)

        return ft.Container(
            content=ft.Column(
                [
                    # File selection section
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text(
                                    "File Selection", size=18, weight=ft.FontWeight.BOLD
                                ),
                                ft.Row(
                                    [
                                        ft.ElevatedButton(
                                            "Select Original Audio (MP3)",
                                            on_click=self.select_compare_original,
                                        ),
                                        ft.Container(
                                            self.compare_original_text, expand=True
                                        ),
                                    ]
                                ),
                                ft.Row(
                                    [
                                        ft.ElevatedButton(
                                            "Select Modified Audio (MP3)",
                                            on_click=self.select_compare_modified,
                                        ),
                                        ft.Container(
                                            self.compare_modified_text, expand=True
                                        ),
                                    ]
                                ),
                            ]
                        ),
                        padding=ft.padding.all(10),
                        border=ft.border.all(1, "grey"),
                        border_radius=5,
                    ),
                    # Results section
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text("Results", size=18, weight=ft.FontWeight.BOLD),
                                self.psnr_result_text,
                            ]
                        ),
                        padding=ft.padding.all(10),
                        border=ft.border.all(1, "grey"),
                        border_radius=5,
                    ),
                    # Action button
                    ft.Container(
                        content=ft.ElevatedButton(
                            "Compare Audio Files (PSNR)",
                            color="white",
                            bgcolor="orange",
                            on_click=self.perform_compare,
                        ),
                        alignment=ft.alignment.center,
                        padding=ft.padding.all(10),
                    ),
                ]
            ),
            padding=ft.padding.all(10),
        )

    def create_player_tab(self):
        """Create the audio player tab content."""

        # Player controls
        self.player_file_text = ft.Text("No audio file loaded", size=12)

        self.play_button = ft.ElevatedButton("Play", on_click=self.toggle_play)
        self.stop_button = ft.ElevatedButton("Stop", on_click=self.stop_audio)

        # Volume slider
        self.volume_slider = ft.Slider(
            min=0,
            max=100,
            value=50,
            divisions=100,
            label="Volume: {value}%",
            on_change=self.on_volume_change,
        )

        # Seek bar
        self.seek_slider = ft.Slider(
            min=0,
            max=100,
            value=0,
            divisions=1000,
            label="Position",
            on_change=self.on_seek_change,
            disabled=True,
        )

        self.position_text = ft.Text("00:00 / 00:00", size=14)

        # Position tracking thread
        self.position_thread: Optional[threading.Thread] = None
        self.stop_position_thread = False

        return ft.Container(
            content=ft.Column(
                [
                    # File selection section
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text(
                                    "Audio Player", size=18, weight=ft.FontWeight.BOLD
                                ),
                                ft.Row(
                                    [
                                        ft.ElevatedButton(
                                            "Load Audio File",
                                            on_click=self.select_player_audio,
                                        ),
                                        ft.Container(
                                            self.player_file_text, expand=True
                                        ),
                                    ]
                                ),
                            ]
                        ),
                        padding=ft.padding.all(10),
                        border=ft.border.all(1, "grey"),
                        border_radius=5,
                    ),
                    # Player controls section
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text("Controls", size=18, weight=ft.FontWeight.BOLD),
                                ft.Row(
                                    [
                                        self.play_button,
                                        self.stop_button,
                                    ],
                                    alignment=ft.MainAxisAlignment.CENTER,
                                ),
                                ft.Row(
                                    [
                                        ft.Text("Volume:", size=14),
                                        ft.Container(self.volume_slider, expand=True),
                                    ]
                                ),
                                ft.Row(
                                    [
                                        ft.Text("Position:", size=14),
                                        ft.Container(self.seek_slider, expand=True),
                                    ]
                                ),
                                ft.Container(
                                    content=self.position_text,
                                    alignment=ft.alignment.center,
                                ),
                            ]
                        ),
                        padding=ft.padding.all(10),
                        border=ft.border.all(1, "grey"),
                        border_radius=5,
                    ),
                ]
            ),
            padding=ft.padding.all(10),
        )

    # File selection methods
    def select_cover_audio(self, e):
        def on_result(result: ft.FilePickerResultEvent):
            if result.files:
                self.cover_audio_path = result.files[0].path
                self.cover_audio_text.value = os.path.basename(self.cover_audio_path)
                self.page.update()

        file_picker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(file_picker)
        self.page.update()
        file_picker.pick_files(
            dialog_title="Select Cover Audio File",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["mp3"],
        )

    def select_secret_file(self, e):
        def on_result(result: ft.FilePickerResultEvent):
            if result.files:
                self.secret_file_path = result.files[0].path
                self.secret_file_text.value = os.path.basename(self.secret_file_path)
                self.page.update()

        file_picker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(file_picker)
        self.page.update()
        file_picker.pick_files(dialog_title="Select Secret File")

    def select_output_audio(self, e):
        def on_result(result: ft.FilePickerResultEvent):
            if result.path:
                self.output_audio_path = result.path
                if not self.output_audio_path.endswith(".mp3"):
                    self.output_audio_path += ".mp3"
                self.output_audio_text.value = os.path.basename(self.output_audio_path)
                self.page.update()

        file_picker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(file_picker)
        self.page.update()
        file_picker.save_file(
            dialog_title="Save Stego Audio As",
            file_name="stego_output.mp3",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["mp3"],
        )

    def select_stego_audio(self, e):
        def on_result(result: ft.FilePickerResultEvent):
            if result.files:
                self.stego_audio_path = result.files[0].path
                self.stego_audio_text.value = os.path.basename(self.stego_audio_path)
                self.page.update()

        file_picker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(file_picker)
        self.page.update()
        file_picker.pick_files(
            dialog_title="Select Stego Audio File",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["mp3"],
        )

    def select_extract_output(self, e):
        def on_result(result: ft.FilePickerResultEvent):
            if result.path:
                self.extract_output_folder = result.path
                self.extract_output_text.value = os.path.basename(
                    self.extract_output_folder
                )
                self.page.update()

        file_picker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(file_picker)
        self.page.update()
        file_picker.get_directory_path(dialog_title="Select Output Folder")

    def select_compare_original(self, e):
        def on_result(result: ft.FilePickerResultEvent):
            if result.files:
                self.compare_original_path = result.files[0].path
                self.compare_original_text.value = os.path.basename(
                    self.compare_original_path
                )
                self.page.update()

        file_picker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(file_picker)
        self.page.update()
        file_picker.pick_files(
            dialog_title="Select Original Audio File",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["mp3"],
        )

    def select_compare_modified(self, e):
        def on_result(result: ft.FilePickerResultEvent):
            if result.files:
                self.compare_modified_path = result.files[0].path
                self.compare_modified_text.value = os.path.basename(
                    self.compare_modified_path
                )
                self.page.update()

        file_picker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(file_picker)
        self.page.update()
        file_picker.pick_files(
            dialog_title="Select Modified Audio File",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["mp3"],
        )

    def select_player_audio(self, e):
        def on_result(result: ft.FilePickerResultEvent):
            if result.files:
                file_path = result.files[0].path
                self.player_file_text.value = f"Loaded: {Path(file_path).name}"
                self.player_file_text.color = "green"
                self.page.update()

                if audio_player.load_file(file_path):
                    self.seek_slider.disabled = False
                    self.seek_slider.max = audio_player.get_duration()
                    self.page.update()
                else:
                    self.player_file_text.value = (
                        f"Error loading: {Path(file_path).name}"
                    )
                    self.player_file_text.color = "red"
                    self.page.update()

        file_picker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(file_picker)
        self.page.update()
        file_picker.pick_files(
            dialog_title="Select Audio File to Play",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["mp3", "wav", "ogg"],
        )

    # Event handlers
    def on_encrypt_change(self, e):
        self.update_key_field()

    def on_random_change(self, e):
        self.update_key_field()

    def on_extract_encrypt_change(self, e):
        self.update_extract_key_field()

    def on_extract_random_change(self, e):
        self.update_extract_key_field()

    def update_key_field(self):
        needs_key = self.encrypt_checkbox.value or self.random_position_checkbox.value
        self.key_textfield.disabled = not needs_key
        self.page.update()

    def update_extract_key_field(self):
        needs_key = (
            self.extract_encrypt_checkbox.value or self.extract_random_checkbox.value
        )
        self.extract_key_textfield.disabled = not needs_key
        self.page.update()

    # Audio player methods
    def toggle_play(self, e):
        if audio_player.is_file_playing():
            audio_player.pause()
            self.play_button.text = "Play"
        else:
            if audio_player.play():
                self.play_button.text = "Pause"
                self.start_position_tracking()
            else:
                self.show_error("Failed to play audio")
        self.page.update()

    def stop_audio(self, e):
        audio_player.stop()
        self.play_button.text = "Play"
        self.seek_slider.value = 0
        self.page.update()

    def on_volume_change(self, e):
        volume = self.volume_slider.value / 100.0
        audio_player.set_volume(volume)

    def on_seek_change(self, e):
        if audio_player.get_duration() > 0:
            position = (self.seek_slider.value / 100.0) * audio_player.get_duration()
            audio_player.seek(position)

    def start_position_tracking(self):
        self.stop_position_thread = False
        if self.position_thread is None or not self.position_thread.is_alive():
            self.position_thread = threading.Thread(target=self.update_position_display)
            self.position_thread.daemon = True
            self.position_thread.start()

    def update_position_display(self):
        while not self.stop_position_thread:
            position = audio_player.get_position()
            duration = audio_player.get_duration()

            pos_str = self.format_time(position)
            dur_str = self.format_time(duration)

            self.position_text.value = f"{pos_str} / {dur_str}"

            # Update seek slider
            if duration > 0:
                self.seek_slider.value = (position / duration) * 100

            if not audio_player.is_file_playing() and position > 0:
                self.play_button.text = "Play"

            self.page.update()
            import time

            time.sleep(0.5)

    def format_time(self, seconds: float) -> str:
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"

    # Main operations
    def perform_embed(self, e):
        """Perform the embedding operation."""
        if not self.validate_embed_inputs():
            return

        def embed_worker():
            try:
                self.set_status("Embedding...", True)

                # Get parameters
                lsb_count = int(self.lsb_count_dropdown.value or "2")
                encrypt = self.encrypt_checkbox.value
                random_pos = self.random_position_checkbox.value
                key = self.key_textfield.value if (encrypt or random_pos) else None

                # Perform embedding
                embed(
                    audio_path=self.cover_audio_path,
                    file_to_hide_path=self.secret_file_path,
                    output_path=self.output_audio_path,
                    bits_per_sample=lsb_count,
                    encrypt=encrypt,
                    key=key,
                    random_position=random_pos,
                )

                self.set_status("Embedding completed successfully!", False, "green")
                self.show_notification("✅ Secret file embedded successfully!", "green")

            except Exception as ex:
                error_msg = f"Embedding failed: {str(ex)}"
                self.set_status(error_msg, False, "red")
                self.show_notification(f"❌ {error_msg}", "red")

        threading.Thread(target=embed_worker, daemon=True).start()

    def perform_extract(self, e):
        """Perform the extraction operation."""
        if not self.validate_extract_inputs():
            return

        def extract_worker():
            try:
                self.set_status("Extracting...", True)

                # Get parameters
                encrypted = self.extract_encrypt_checkbox.value
                if encrypted is None:
                    encrypted = False
                random_pos = self.extract_random_checkbox.value
                key = (
                    self.extract_key_textfield.value
                    if (encrypted or random_pos)
                    else None
                )

                # Perform extraction
                extracted_file = extract(
                    stego_audio_path=self.stego_audio_path,
                    output_path=self.extract_output_folder,
                    encrypted=encrypted,
                    key=key,
                    random_position=random_pos,
                )

                self.set_status(
                    f"Extraction completed! File saved: {os.path.basename(extracted_file)}",
                    False,
                    "green",
                )
                self.show_notification(
                    f"✅ Secret file extracted successfully! Saved: {os.path.basename(extracted_file)}",
                    "green",
                )

            except Exception as ex:
                error_msg = f"Extraction failed: {str(ex)}"
                self.set_status(error_msg, False, "red")
                self.show_notification(f"❌ {error_msg}", "red")

        threading.Thread(target=extract_worker, daemon=True).start()

    def perform_compare(self, e):
        """Perform the PSNR comparison."""
        if not self.validate_compare_inputs():
            return

        def compare_worker():
            try:
                self.set_status("Comparing audio files...", True)

                # Perform comparison
                psnr_value = compare_mp3_files(
                    Path(self.compare_original_path), Path(self.compare_modified_path)
                )

                # Display result
                self.psnr_result_text.value = f"PSNR: {psnr_value:.4f} dB"
                self.psnr_result_text.color = "blue"

                self.set_status("Comparison completed successfully!", False, "green")

                # Show notification with quality assessment
                if psnr_value > 60:
                    quality = "Excellent quality preservation!"
                elif psnr_value > 40:
                    quality = "Good quality preservation!"
                elif psnr_value > 20:
                    quality = "Moderate quality preservation"
                else:
                    quality = "Low quality preservation"

                self.show_notification(
                    f"✅ PSNR: {psnr_value:.2f} dB - {quality}", "blue"
                )

            except Exception as ex:
                error_msg = f"Comparison failed: {str(ex)}"
                self.set_status(error_msg, False, "red")
                self.psnr_result_text.value = "Comparison failed"
                self.psnr_result_text.color = "red"
                self.show_notification(f"❌ {error_msg}", "red")

        threading.Thread(target=compare_worker, daemon=True).start()

    # Validation methods
    def validate_embed_inputs(self) -> bool:
        if not self.cover_audio_path:
            self.show_error("Please select a cover audio file")
            return False
        if not self.secret_file_path:
            self.show_error("Please select a secret file")
            return False
        if not self.output_audio_path:
            self.show_error("Please select an output location")
            return False
        if (
            self.encrypt_checkbox.value or self.random_position_checkbox.value
        ) and not self.key_textfield.value:
            self.show_error("Please provide a key for encryption/randomization")
            return False
        return True

    def validate_extract_inputs(self) -> bool:
        if not self.stego_audio_path:
            self.show_error("Please select a stego audio file")
            return False
        if not self.extract_output_folder:
            self.show_error("Please select an output folder")
            return False
        if (
            self.extract_encrypt_checkbox.value or self.extract_random_checkbox.value
        ) and not self.extract_key_textfield.value:
            self.show_error("Please provide a key for decryption/randomization")
            return False
        return True

    def validate_compare_inputs(self) -> bool:
        if not self.compare_original_path:
            self.show_error("Please select the original audio file")
            return False
        if not self.compare_modified_path:
            self.show_error("Please select the modified audio file")
            return False
        return True

    # Utility methods
    def set_status(
        self, message: str, show_progress: bool = False, color: str = "blue"
    ):
        self.status_text.value = message
        self.status_text.color = color
        self.progress_bar.visible = show_progress
        self.page.update()

    def show_error(self, message: str):
        self.set_status(f"Error: {message}", False, "red")

    def cleanup(self):
        """Clean up resources."""
        self.stop_position_thread = True
        audio_player.cleanup()


def run_gui(page: ft.Page):
    app = GUI(page)

    # Handle window close
    def on_window_event(e):
        if e.data == "close":
            app.cleanup()
            page.window.destroy()

    page.window.on_event = on_window_event
    page.window.prevent_close = False
