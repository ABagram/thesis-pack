import sys
import os
import json
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget,
                             QHBoxLayout, QVBoxLayout, QPushButton, 
                             QLabel, QFrame, QScrollArea, QFileDialog)
from sidebar import OrderQueue
from components.navigation_sidebar import NavigationSidebar
from main_content_widget import MainContentWidget
from load_font_folder import load_font_folder
from string import Template
from branding import *

class MainWindow(QMainWindow):
    """The orchestration window coordinating communication between the Sidebar and Main Panel."""
    def __init__(
        self,
        order_queue_position="right",
        navigation_position="left"
    ):
        super().__init__()
        self.setWindowTitle("Automation Pipeline Dashboard")
        self.resize(1000, 650)
        self.order_queue_position = order_queue_position
        self.navigation_position = navigation_position

        # Single Source of Truth for Directory
        self.default_batch_directory = os.path.join(os.path.expanduser("~"), "Desktop", "Orders_Root", "Active_Batch")
        os.makedirs(self.default_batch_directory, exist_ok=True)

        self.init_ui()

        # Core Asynchronous Background Scanner
        self.scan_timer = QTimer(self)
        self.scan_timer.timeout.connect(
            self.order_queue.scan_active_subdirectories
        )
        self.scan_timer.start(1000)

    def init_ui(self):
        self.central_widget = QWidget()
        self.central_widget.setObjectName("MainWindow")
        self.setCentralWidget(self.central_widget)

        # Instantiate modular components
        self.order_queue = OrderQueue(
            self.default_batch_directory,
            position=self.order_queue_position,
        )
        self.sidebar = self.order_queue
        self.navigation_sidebar = NavigationSidebar(
            position=self.navigation_position
        )
        self.main_content = MainContentWidget()

        self._compose_workspace()

        # Cross-Widget Signal Interceptions
        self.order_queue.order_selected.connect(self.handle_order_selection)
        self.navigation_sidebar.view_selected.connect(
            self.main_content.show_view
        )
        self.main_content.hardware_trigger_clicked.connect(self.handle_esp_hardware_trigger)
        self.main_content.order_state_updated.connect(self.handle_order_state_update)

    def handle_order_selection(self, order_id):
        """Passes directory context from sidebar over to the main canvas."""
        self.main_content.update_display_details(
            order_id,
            self.order_queue.active_main_directory
        )
        self.order_queue.sync_order_widget_state(order_id)

    def handle_order_state_update(self, order_id, state_data):
        """Syncs sidebar order widget when main content updates the order state."""
        self.order_queue.sync_order_widget_state(order_id)

    def _compose_workspace(self):
        queue_is_horizontal = self.order_queue_position in {
            "top",
            "bottom",
        }
        navigation_is_horizontal = self.navigation_position in {
            "top",
            "bottom",
        }

        main_layout_type = QVBoxLayout if queue_is_horizontal else QHBoxLayout
        self.main_layout = main_layout_type(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        if queue_is_horizontal:
            workspace = QWidget()
            workspace_layout = self._make_navigation_layout(
                workspace,
                navigation_is_horizontal,
            )
            if self.order_queue_position == "top":
                self.main_layout.addWidget(self.order_queue)
                self.main_layout.addWidget(workspace)
            else:
                self.main_layout.addWidget(workspace)
                self.main_layout.addWidget(self.order_queue)
            return

        workspace = QWidget()
        workspace_layout = self._make_navigation_layout(
            workspace,
            navigation_is_horizontal,
        )
        if self.order_queue_position == "left":
            self.main_layout.addWidget(self.order_queue)
            self.main_layout.addWidget(workspace)
        else:
            self.main_layout.addWidget(workspace)
            self.main_layout.addWidget(self.order_queue)

    def _make_navigation_layout(self, workspace, navigation_is_horizontal):
        layout = QVBoxLayout(workspace) if navigation_is_horizontal else QHBoxLayout(workspace)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        if self.navigation_position in {"left", "top"}:
            layout.addSpacing(20)
            layout.addWidget(self.navigation_sidebar)
            layout.addSpacing(20)
            layout.addWidget(self.main_content, 1)
        else:
            layout.addWidget(self.main_content, 1)
            layout.addWidget(self.navigation_sidebar)
        return layout

    def handle_esp_hardware_trigger(self):
        """Mimics the ESP creating a subdirectory instantly on button-press."""
        target_dir = self.order_queue.active_main_directory
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
    
    app.setFont(QFont("Poppins", 10))
    
    try:
        with open("style.qss", "r") as f:
            qss_template = f.read()
            
        # Use Template so normal CSS braces don't crash it
        template = Template(qss_template)
        app.setStyleSheet(template.safe_substitute(**globals()))
    except FileNotFoundError:
        print("Warning: style.qss file not found. Running with default styles.")

    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()