import sys
import os
import json
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                             QHBoxLayout, QVBoxLayout, QPushButton, 
                             QLabel, QFrame, QScrollArea, QFileDialog)
from order_item_widget import OrderItemWidget
from sidebar import SidebarWidget
from main_content_widget import MainContentWidget
from load_font_folder import load_font_folder

class MainWindow(QMainWindow):
    """The orchestration window coordinating communication between the Sidebar and Main Panel."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Automation Pipeline Dashboard")
        self.resize(1000, 650)

        # Single Source of Truth for Directory
        self.default_batch_directory = os.path.join(os.path.expanduser("~"), "Desktop", "Orders_Root", "Active_Batch")
        os.makedirs(self.default_batch_directory, exist_ok=True)

        self.init_ui()

        # Core Asynchronous Background Scanner
        self.scan_timer = QTimer(self)
        self.scan_timer.timeout.connect(self.sidebar.scan_active_subdirectories)
        self.scan_timer.start(1000)

    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Instantiate modular components
        self.sidebar = SidebarWidget(self.default_batch_directory)
        self.main_content = MainContentWidget()

        self.main_layout.addWidget(self.sidebar)
        self.main_layout.addWidget(self.main_content)

        # Cross-Widget Signal Interceptions
        self.sidebar.order_selected.connect(self.handle_order_selection)
        self.main_content.hardware_trigger_clicked.connect(self.handle_esp_hardware_trigger)
        self.main_content.order_state_updated.connect(self.handle_order_state_update)

    def handle_order_selection(self, order_id):
        """Passes directory context from sidebar over to the main canvas."""
        self.main_content.update_display_details(order_id, self.sidebar.active_main_directory)
        self.sidebar.sync_order_widget_state(order_id)

    def handle_order_state_update(self, order_id, state_data):
        """Syncs sidebar order widget when main content updates the order state."""
        self.sidebar.sync_order_widget_state(order_id)

    def handle_esp_hardware_trigger(self):
        """Mimics the ESP creating a subdirectory instantly on button-press."""
        target_dir = self.sidebar.active_main_directory
        try:
            existing_orders = [d for d in os.listdir(target_dir) if os.path.isdir(os.path.join(target_dir, d))]
        except OSError:
            return

        next_num = len(existing_orders) + 1
        new_order_name = f"order_{next_num}"
        new_order_path = os.path.join(target_dir, new_order_name)
        
        os.makedirs(new_order_path, exist_ok=True)
        
        # Step 1: Simulate immediate image drop
        with open(os.path.join(new_order_path, "cv_capture.jpg"), "w") as img_placeholder:
            img_placeholder.write("") 
            
        # Step 2: Initialize manifest
        initial_manifest = {"stage": "snapshot_pending", "current_item": 0, "total_items": 0}
        with open(os.path.join(new_order_path, "order_manifest.json"), "w") as f:
            json.dump(initial_manifest, f, indent=4)

def main():
    app = QApplication(sys.argv)
    
    load_font_folder("./fonts/Poppins")
    
    # Ensure Poppins is the app default font after loading the font resources
    app.setFont(QFontDatabase.font("Poppins", "Medium", 10))
    
    try:
        with open("style.qss", "r") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        print("Warning: style.qss file not found. Running with default styles.")
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()