import sys
import os
import json
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                             QHBoxLayout, QVBoxLayout, QPushButton, 
                             QLabel, QFrame, QScrollArea, QFileDialog, QTabWidget, QListWidget, QComboBox, QStackedWidget)
from order_item_widget import OrderItemWidget

class SidebarWidget(QFrame):
    """Handles the collapsible pipeline sidebar, order list scanning, and batch selection."""
    order_selected = pyqtSignal(str)  # Emitted when an order card is clicked

    def __init__(self, initial_batch_dir):
        super().__init__()
        self.setObjectName("Sidebar")
        self.active_main_directory = initial_batch_dir
        self.known_orders = {}
        self.sidebar_is_collapsed = False
        
        self.sidebar_expanded_width = 340
        self.sidebar_collapsed_width = 70
        self.setMinimumWidth(self.sidebar_expanded_width)
        self.setMaximumWidth(self.sidebar_expanded_width)

        self.init_ui()

    def init_ui(self):
        self.sidebar_layout = QVBoxLayout(self)
        self.sidebar_layout.setContentsMargins(8, 10, 8, 10)
        self.sidebar_layout.setSpacing(10)

        # Toggle button
        self.btn_toggle = QPushButton(" ☰   Collapse Pipeline")
        self.sidebar_layout.addWidget(self.btn_toggle)
      
        # Batch info label
        self.batch_frame = QFrame()
        self.batch_frame.setObjectName("BatchFrame")
        
        self.batch_info_layout = QVBoxLayout(self.batch_frame)
        self.batch_info_layout.setSpacing(4)  # Tight gap between header line and path string
        
        # Header Row (Title + Stretch Space + Button)
        header_row_layout = QHBoxLayout()
        header_row_layout.setSpacing(6)
        
        self.batch_title_label = QLabel("<b>Active Batch</b>")
        self.batch_title_label.setStyleSheet("font-size: 13px; color: #181818;")
        
        self.batch_count_label = QLabel("0")
        self.batch_count_label.setStyleSheet("""
            font-size: 11px; 
            font-weight: bold; 
            color: #34495e; 
            background-color: rgba(52, 73, 94, 0.15); 
            border: 1px solid #34495e; 
            border-radius: 9px; 
            padding: 1px 7px;
        """)
        
        self.btn_set_active_batch = QPushButton("Change")
        self.btn_set_active_batch.clicked.connect(self.change_active_batch_directory)
        
        header_row_layout.addWidget(self.batch_title_label)
        header_row_layout.addWidget(self.batch_count_label)
        header_row_layout.addStretch()  # Pushes the change button all the way to the right
        header_row_layout.addWidget(self.btn_set_active_batch)
        
        # Path Display (Truncated to last 2 folders below the header)
        self.batch_info_label = QLabel()
        self.batch_info_label.setWordWrap(True)
        self.batch_info_label.setStyleSheet(
            "font-size: 12px; color: #181818; padding: 6px; background: #efedeb; border-radius: 4px;"
        )
        # Helper function to truncate and set path display text
        self.update_path_display(self.active_main_directory)

        # Assemble the layouts
        self.batch_info_layout.addLayout(header_row_layout)
        self.batch_info_layout.addWidget(self.batch_info_label)
        self.sidebar_layout.addWidget(self.batch_frame)
        
        # Scroll Area for tracking child subdirectories
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: transparent; border: none;")
        
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(6)
        self.scroll_layout.addStretch()
        
        self.scroll.setWidget(self.scroll_content)
        self.sidebar_layout.addWidget(self.scroll)
        
        # --- Updated Queue Frame with Dropdown ---
        self.queue_frame = QFrame()
        self.queue_frame.setObjectName("QueueFrame")
        self.queue_layout = QVBoxLayout(self.queue_frame)
        self.queue_layout.setContentsMargins(6, 8, 6, 6)
        self.queue_layout.setSpacing(6)

        # Header Row: Title + Dropdown Combo
        queue_header_layout = QHBoxLayout()
        
        self.queue_title = QLabel("<b>Production Queue</b>")
        queue_header_layout.addWidget(self.queue_title)
        
        self.queue_dropdown = QComboBox()
        self.queue_dropdown.setStyleSheet("""
            QComboBox { 
                font-size: 11px; 
                padding: 2px 5px; 
                min-width: 90px;
                max-width: 120px;
            }
        """)
        self.queue_dropdown.addItems(["Capture", "CV", "Sizing", "Cut"])
        queue_header_layout.addWidget(self.queue_dropdown)
        
        # Add the header row to the main queue layout
        self.queue_layout.addLayout(queue_header_layout)

        # Create Stacked Widget to host the different list views
        self.queue_stack = QStackedWidget()
        
        self.queue_capture_list = QListWidget()
        self.queue_cv_list = QListWidget()
        self.queue_sizing_list = QListWidget()
        self.queue_cut_list = QListWidget()

        # Add lists to the stack (index order matches the dropdown items array)
        self.queue_stack.addWidget(self.queue_capture_list) # Index 0
        self.queue_stack.addWidget(self.queue_cv_list)      # Index 1
        self.queue_stack.addWidget(self.queue_sizing_list)  # Index 2
        self.queue_stack.addWidget(self.queue_cut_list)     # Index 3

        self.queue_layout.addWidget(self.queue_stack)
        self.sidebar_layout.addWidget(self.queue_frame)
        
        # Connect the dropdown index changes to the stack controller
        self.queue_dropdown.currentIndexChanged.connect(self.queue_stack.setCurrentIndex)
        self.sidebar_layout.addWidget(self.queue_frame)
        
        # Event connections
        self.btn_toggle.clicked.connect(self.toggle_sidebar)

    def update_path_display(self, path):
        """Truncates the path to show only the last two directories for clean UI spacing."""
        if not path:
            self.batch_info_label.setText("None Selected")
            return

        # Normalize paths to clear double slashes or trailing slash issues
        normalized_path = os.path.normpath(path)
        parts = normalized_path.split(os.sep)

        # Filter out empty strings caused by root split variants
        parts = [p for p in parts if p]

        if len(parts) >= 2:
            display_text = f".../{parts[-2]}/{parts[-1]}"
        elif len(parts) == 1:
            display_text = parts[0]
        else:
            display_text = path

        self.batch_info_label.setText(display_text)
        
    def change_active_batch_directory(self):
        """Forces the dashboard to redirect focus onto exactly one main directory."""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Active Main Batch Folder", self.active_main_directory)
        if dir_path:
            self.active_main_directory = dir_path
            # Refresh the truncated path display and tooltip
            self.update_path_display(self.active_main_directory)
            self.batch_info_label.setToolTip(self.active_main_directory)
            self.known_orders.clear()
            
            # Wipe UI clean for new batch folders
            for i in reversed(range(self.scroll_layout.count() - 1)): 
                widget = self.scroll_layout.itemAt(i).widget()
                if widget:
                    widget.setParent(None)
            self.scan_active_subdirectories()

    def scan_active_subdirectories(self):
        """Scans the active subdirectories directly."""
        # Ensure displayed path is refreshed each scan (handles UI refreshes)
        self.update_path_display(self.active_main_directory)
        if not os.path.exists(self.active_main_directory):
            self.batch_count_label.setText("0")
            # If directory was removed/renamed externally, indicate missing path
            self.batch_info_label.setToolTip(self.active_main_directory)
            return

        try:
            subdirs = [d for d in os.listdir(self.active_main_directory) if os.path.isdir(os.path.join(self.active_main_directory, d))]
        except OSError:
            self.batch_count_label.setText("0")
            return

        self.batch_count_label.setText(str(len(subdirs)))
        
        for order_dir in subdirs:
            manifest_path = os.path.join(self.active_main_directory, order_dir, "order_manifest.json")
            payload = {"stage": "snapshot_pending", "current_item": 0, "total_items": 0}
            
            if os.path.exists(manifest_path):
                try:
                    with open(manifest_path, 'r') as f:
                        payload = json.load(f)
                except Exception:
                    continue  # Ignore brief cross-process conflicts

            state_key = f"{payload.get('stage')}_{payload.get('current_item')}_{payload.get('total_items')}"

            if order_dir not in self.known_orders:
                order_widget = OrderItemWidget(order_dir, payload, os.path.join(self.active_main_directory, order_dir))
                order_widget.set_collapsed_mode(self.sidebar_is_collapsed)
                order_widget.clicked.connect(lambda checked, od=order_dir: self.order_selected.emit(od))
                
                self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, order_widget)
                self.known_orders[order_dir] = (order_widget, state_key)
            else:
                widget_ref, old_key = self.known_orders[order_dir]
                if old_key != state_key:
                    widget_ref.update_state(payload)
                    self.known_orders[order_dir] = (widget_ref, state_key)

    def toggle_sidebar(self):
        current_width = self.width()
        if current_width > self.sidebar_collapsed_width:
            target_width = self.sidebar_collapsed_width
            self.sidebar_is_collapsed = True
            self.btn_toggle.setText("☰")
            self.batch_frame.hide()
            self.btn_set_active_batch.setText("📁")
        else:
            target_width = self.sidebar_expanded_width
            self.sidebar_is_collapsed = False
            self.btn_toggle.setText(" ☰   Collapse Pipeline")
            self.batch_frame.show()
            self.btn_set_active_batch.setText("Change")

        for order_id, (widget_ref, _) in self.known_orders.items():
            widget_ref.set_collapsed_mode(self.sidebar_is_collapsed)

        self.animation = QPropertyAnimation(self, b"minimumWidth")
        self.animation.setDuration(180)
        self.animation.setStartValue(current_width)
        self.animation.setEndValue(target_width)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.animation.valueChanged.connect(lambda val: self.setMaximumWidth(val))
        self.animation.start()

    def sync_order_widget_state(self, order_id):
        """Updates a specific order widget's visual state from its manifest file."""
        if order_id not in self.known_orders:
            return
        
        widget_ref, _ = self.known_orders[order_id]
        manifest_path = os.path.join(self.active_main_directory, order_id, "order_manifest.json")
        
        try:
            if os.path.exists(manifest_path):
                with open(manifest_path, 'r') as f:
                    payload = json.load(f)
                    widget_ref.update_state(payload)
        except Exception:
            pass
