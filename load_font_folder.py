import os
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QPushButton, QWidget
from PyQt6.QtGui import QFontDatabase

def load_font_folder(folder_path):
    """Loops through a folder and registers all Poppins TTF files into PyQt6."""
    if not os.path.exists(folder_path):
        print(f"Error: The folder '{folder_path}' does not exist.")
        return

    for filename in os.listdir(folder_path):
        if filename.lower().endswith(".ttf"):
            file_path = os.path.join(folder_path, filename)
            
            # PyQt6 static method call
            font_id = QFontDatabase.addApplicationFont(file_path)
            
            if font_id == -1:
                print(f"❌ Failed to load: {filename}")
            else:
                print(f"✅ Loaded: {filename}")