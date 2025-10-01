import sys
from pathlib import Path

# Add the src directory to Python path
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

try:
    # Import and run the GUI
    from gui_simple import main
    import flet as ft

    print("Starting Audio Steganography GUI...")
    print("Make sure you have installed all requirements:")
    print("pip install -r requirements.txt")
    print("")

    ft.app(target=main)

except ImportError as e:
    print(f"Import error: {e}")
    print("\nPlease install the required dependencies:")
    print("pip install -r requirements.txt")
    print("\nRequired packages:")
    print("- flet")
    print("- pygame")
    print("- librosa")
    print("- numpy")
    sys.exit(1)

except Exception as e:
    print(f"Error starting GUI: {e}")
    sys.exit(1)
