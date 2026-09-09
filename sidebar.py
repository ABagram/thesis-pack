import sys
import os
import json
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                             QHBoxLayout, QVBoxLayout, QPushButton, 
                             QLabel, QFrame, QScrollArea, QFileDialog, QTabWidget, QListWidget, QComboBox, QStackedWidget, QScrollArea)
from order_item_widget import OrderItemWidget
from load_icon import load_icon

ICON_ASSET_PATHS = {
    "camera": "icons/linked_camera.svg",
    "pc": "icons/desktop_windows.svg",
    "cnc": "icons/cnc.svg",
    "wifi": "icons/wifi.svg",
    "lock": "icons/lock.svg",
    "copy": "icons/content_copy.svg",
    "network_ok": "icons/wifi.svg",
    "network_warning": "icons/warning.svg",
    "folder": "icons/folder.svg"
}

class SidebarWidget(QFrame):
    """Handles the collapsible pipeline sidebar, order list scanning, and batch selection."""
    order_selected = pyqtSignal(str)  # Emitted when an order card is clicked

    def __init__(self, initial_batch_dir):
        super().__init__()
        self.setObjectName("Sidebar")
        
        self.active_main_directory = initial_batch_dir
        self.order_simple_status = {}
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

        self.folder_icon = QLabel() 
        self.folder_icon.setPixmap(load_icon(ICON_ASSET_PATHS["folder"], size=14, color="#166534"))
        self.folder_icon.setStyleSheet("font-size: 14px; color: #64748b;")
        
        self.batch_title_label = QLabel("<b>Active Batch</b>")
        self.batch_title_label.setObjectName("BatchTitle")
        
        self.batch_count_label = QLabel("0")
        self.batch_count_label.setObjectName("BatchCount")
        
        self.btn_set_active_batch = QPushButton("Change")
        self.btn_set_active_batch.clicked.connect(self.change_active_batch_directory)

        header_row_layout.addWidget(self.folder_icon)
        header_row_layout.addWidget(self.batch_title_label)
        header_row_layout.addWidget(self.batch_count_label)
        header_row_layout.addStretch()  # Pushes the change button all the way to the right
        header_row_layout.addWidget(self.btn_set_active_batch)
        
        # Path Display (Truncated to last 2 folders below the header)
        self.batch_info_label = QLabel()
        self.batch_info_label.setObjectName("BatchInfo")
        self.batch_info_label.setWordWrap(True)
        
        # Helper function to truncate and set path display text
        self.update_path_display(self.active_main_directory)

        # Assemble the layouts
        self.batch_info_layout.addLayout(header_row_layout)
        self.batch_info_layout.addWidget(self.batch_info_label)
        self.sidebar_layout.addWidget(self.batch_frame)

        self.order_queue_label = QLabel("<b>Order Queue</b>")
        self.order_queue_label.setStyleSheet("font-size: 12px; color: #181818;")
        self.sidebar_layout.addWidget(self.order_queue_label)
        
        # Scroll Area for tracking child subdirectories
        # --- Order Filter Controls (All / In Progress / In Queue)
        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)
        filter_label = QLabel("Filter:")
        filter_label.setStyleSheet("font-size:11px; color: #181818;")
        self.order_filter_dropdown = QComboBox()
        self.order_filter_dropdown.addItems(["All", "In Progress", "In Queue"])
        self.order_filter_dropdown.currentIndexChanged.connect(lambda _: self.apply_order_filter())

        filter_row.addWidget(filter_label)
        filter_row.addWidget(self.order_filter_dropdown)
        filter_row.addStretch()
        self.sidebar_layout.addLayout(filter_row)

        self.order_scroll_area = QScrollArea()
        self.order_scroll_area.setWidgetResizable(True)
        self.order_scroll_area.setStyleSheet("background: transparent; border: none;")
        
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(6)
        self.scroll_layout.addStretch()
        
        self.order_scroll_area.setWidget(self.scroll_content)
        self.sidebar_layout.addWidget(self.order_scroll_area)
    
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
            self.order_simple_status.clear()
            
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

            # Classify a simple status for filtering
            simple_status = self._classify_payload_stage(payload)
            self.order_simple_status[order_dir] = simple_status

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

        # Apply current filter after processing the list
        self.apply_order_filter()

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
                    # Update cached simple status and reapply filter
                    self.order_simple_status[order_id] = self._classify_payload_stage(payload)
                    self.apply_order_filter()
        except Exception:
            pass

    def _classify_payload_stage(self, payload: dict) -> str:
        """Return a simplified status used for filtering: 'In Queue', 'In Progress', or 'Completed'."""
        stage = payload.get('stage', 'snapshot_pending')
        if stage in ('snapshot_pending', 'retake'):
            return 'In Queue'
        if stage == 'completed':
            return 'Completed'
        return 'In Progress'

    def apply_order_filter(self):
        """Show/hide order widgets based on the selected filter."""
        sel = self.order_filter_dropdown.currentText() if hasattr(self, 'order_filter_dropdown') else 'All'
        for order_dir, (widget_ref, _) in self.known_orders.items():
            status = self.order_simple_status.get(order_dir, 'In Queue')
            if sel == 'All':
                widget_ref.setVisible(True)
            elif sel == 'In Progress':
                widget_ref.setVisible(status == 'In Progress')
            elif sel == 'In Queue':
                widget_ref.setVisible(status == 'In Queue')
