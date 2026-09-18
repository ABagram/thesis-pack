import sys
import os
import json
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget,
                             QHBoxLayout, QVBoxLayout, QPushButton, 
                             QLabel, QFrame, QScrollArea, QFileDialog)
from components.nav_bar import NavigationSidebar
from main_content_widget import MainContentWidget
from load_font_folder import load_font_folder
from string import Template
from branding import *
from new_order import OrderManager
import threading
from server import run_server

class MainWindow(QMainWindow):
    """The orchestration window coordinating communication between the Sidebar and Main Panel."""
    def __init__(
        self,
        order_queue_position="right",
        navigation_position="left"
    ):
        super().__init__()
        self.setWindowTitle("Automation Pipeline Dashboard")
        
        # RESPONSIVE SIZING: Get the available screen size dynamically
        screen = QApplication.primaryScreen().availableGeometry()
        
        # Set dimensions relative to the screen (e.g., 85% width and height)
        responsive_width = int(screen.width() * 0.85)
        responsive_height = int(screen.height() * 0.85)
        self.resize(responsive_width, responsive_height)
        
        # Center the window on the screen gracefully
        self.move(
            int((screen.width() - responsive_width) / 2),
            int((screen.height() - responsive_height) / 2)
        )

        self.order_queue_position = order_queue_position
        self.navigation_position = navigation_position

        # Single Source of Truth for Directory
        self.default_batch_directory = OrderManager().get_current_batch_directory()
        os.makedirs(self.default_batch_directory, exist_ok=True)

        self.init_ui()

    def init_ui(self):
        self.central_widget = QWidget()
        self.central_widget.setObjectName("MainWindow")
        self.setCentralWidget(self.central_widget)

        # Instantiate modular components
        self.navigation_sidebar = NavigationSidebar(
            position=self.navigation_position
        )
        self.main_content = MainContentWidget(
            default_batch_directory=self.default_batch_directory,
            order_queue_position=self.order_queue_position
        )

        self._compose_workspace()

        # Cross-Widget Signal Interceptions
        self.navigation_sidebar.view_selected.connect(
            self.main_content.show_view
        )
        self.main_content.hardware_trigger_clicked.connect(self.handle_esp_hardware_trigger)

    def _compose_workspace(self):
        navigation_is_horizontal = self.navigation_position in {
            "top",
            "bottom",
        }

        main_layout_type = QVBoxLayout if navigation_is_horizontal else QHBoxLayout
        self.main_layout = main_layout_type(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        if self.navigation_position in {"left", "top"}:
            self.main_layout.addSpacing(20)
            self.main_layout.addWidget(self.navigation_sidebar)
            self.main_layout.addSpacing(20)
            self.main_layout.addWidget(self.main_content, 1)
        else:
            self.main_layout.addWidget(self.main_content, 1)
            self.main_layout.addWidget(self.navigation_sidebar)

    def handle_esp_hardware_trigger(self):
        """Mimics the ESP creating a subdirectory instantly on button-press."""
        order_id, order_path = OrderManager().create_new_order()
        if order_id:
            self.main_content._handle_order_created(order_id, order_path)

def main():
    app = QApplication(sys.argv)

    flask_thread = threading.Thread(
        target=run_server,
        daemon=True
    )
    flask_thread.start()
    
    load_font_folder("./fonts/Poppins")
    app.setFont(QFont("Poppins", 10))
    
    try:
        with open("style.qss", "r") as f:
            qss_template = f.read()
            
        template = Template(qss_template)
        app.setStyleSheet(template.safe_substitute(**globals()))
    except FileNotFoundError:
        print("Warning: style.qss file not found. Running with default styles.")

    window = MainWindow()
    screen_geometry = app.primaryScreen().availableGeometry()

    # Resize window to fit screen if it's too big, keeping a safety margin
    max_width = screen_geometry.width() - 100
    max_height = screen_geometry.height() - 100
    
    # Clamp the window size
    target_width = min(window.width(), max_width)
    target_height = min(window.height(), max_height)
    window.resize(target_width, target_height)

    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()