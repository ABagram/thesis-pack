import os
import shutil
import json
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QPushButton, 
                             QLabel, QFrame, QMessageBox)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPainter, QPen, QColor
from pathlib import Path
from datetime import datetime

class OrderItemWidget(QPushButton):
    """A sleek, minimized order widget with an integrated horizontal canvas pipeline tracker."""
    def __init__(self, order_id, status_data, directory_path="", parent=None):
        super().__init__(parent)
        
        self.setObjectName("MainOrderItemWidget")
        self.setFixedWidth(280) 
        self.setFixedHeight(105)

        self.order_id = order_id
        self.directory_path = os.path.abspath(directory_path) 
        self.active_step_index = 0
        self.num_stages = 8
        
        # Base Widget Layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(14, 12, 14, 12)
        self.main_layout.setSpacing(12)

        # =====================================================================
        # TOP ROW: Order Title & Creation Date
        # =====================================================================
        self.header_layout = QHBoxLayout()
        self.header_layout.setSpacing(8)
        
        self.title_container = QWidget()
        self.title_container.setStyleSheet("background: transparent;")
        self.title_vbox = QVBoxLayout(self.title_container)
        self.title_vbox.setContentsMargins(0, 0, 0, 0)
        self.title_vbox.setSpacing(2)
        
        self.title_label = QLabel(order_id.replace("_", " ").title())
        self.title_label.setObjectName("WidgetTitleLabel")
        self.title_vbox.addWidget(self.title_label)
        
        # Exact requested custom 24h timestamp layout
        created_str = self.get_creation_timestamp()
        self.date_label = QLabel(created_str)
        self.date_label.setObjectName("WidgetDateLabel")
        self.title_vbox.addWidget(self.date_label)
        
        self.header_layout.addWidget(self.title_container)
        self.header_layout.addStretch()
        
        # =====================================================================
        # TOP ROW ACTIONS: Delete Button
        # =====================================================================
        self.badge_text = QLabel("")
        self.badge_text.hide()
        
        self.delete_button = QPushButton("delete_forever", self) 
        self.delete_button.setObjectName("WidgetDeleteButton")
        self.delete_button.setToolTip("Delete Order Permanently")
        self.delete_button.setFixedSize(28, 28)
        self.delete_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.delete_button.clicked.connect(self.confirm_and_delete_subdirectory)
        self.header_layout.addWidget(self.delete_button)
        
        self.main_layout.addLayout(self.header_layout)

        # =====================================================================
        # BOTTOM ROW: Mini Horizontal Step Nodes (Textless)
        # =====================================================================
        self.track_container = QWidget()
        self.track_container.setObjectName("MiniTrackContainer")
        self.track_layout = QHBoxLayout(self.track_container)
        self.track_layout.setContentsMargins(10, 0, 10, 0)
        self.track_layout.setSpacing(0)
        
        self.step_nodes = []
        for i in range(self.num_stages):
            node = QFrame()
            node.setFixedSize(10, 10)
            self.track_layout.addWidget(node)
            self.step_nodes.append(node)
            
            if i < self.num_stages - 1:
                self.track_layout.addStretch(1)
                
        self.main_layout.addWidget(self.track_container)

        self.setStyleSheet("""
            QPushButton#MainOrderItemWidget { 
                background-color: #ffffff; 
                border-radius: 6px; 
                border: 1px solid #e2e8f0;
                text-align: left;
            } 
            QPushButton#MainOrderItemWidget:hover { 
                background-color: #f8fafc; 
                border: 1px solid #cbd5e1;
            }
            QLabel#WidgetTitleLabel {
                color: #1e293b; 
                font-size: 13px; 
                font-weight: bold;
                border: none;
                background: transparent;
            }
            QLabel#WidgetDateLabel {
                color: #64748b;
                font-size: 10px;
                font-weight: normal;
                background: transparent;
            }
            QPushButton#WidgetDeleteButton {
                background-color: transparent;
                border: none;
                font-family: "Material Symbols Rounded";
                font-size: 18px; 
                color: #64748b;
                text-align: center;
            }
            QPushButton#WidgetDeleteButton:hover {
                color: #ef4444;
                background-color: #fee2e2;
                border-radius: 4px;
            }
        """)

        self.update_state(status_data)

    def get_creation_timestamp(self) -> str:
        print("Path:", self.directory_path)
        print("Exists:", os.path.exists(self.directory_path))

        if self.directory_path and os.path.exists(self.directory_path):
            try:
                stat = os.stat(self.directory_path)

                timestamp = getattr(stat, "st_birthtime", stat.st_ctime)

                formatted_date = datetime.fromtimestamp(timestamp).strftime(
                    "%b %#d, %Y %H:%M"
                )

                return f"Created: {formatted_date}"

            except Exception as e:
                print("ERROR:", repr(e))

        return "Created: Unknown"
    def update_state(self, data):
        """Maps directory states to synchronous milestone tracking steps."""
        state = data.get("stage", "snapshot_pending")
        
        # Explicit sync map matching main_content_widget pipeline
        stage_index_map = {
            "snapshot_pending": 0, "retake": 0,
            "counting": 1,         "count_failed": 1,
            "identifying": 2,      "dimensioning": 2,
            "bin_packing": 3,
            "dieline_generation": 4,
            "gcode_generation": 5,
            "gcode_upload": 6,
            "completed": 7
        }

        # Accept direct integers passed via the sync loops, or parse string states
        if isinstance(state, int):
            self.active_step_index = state
        else:
            self.active_step_index = stage_index_map.get(state, 0)

        for idx in range(self.num_stages):
            node = self.step_nodes[idx]
            if idx < self.active_step_index:
                node.setStyleSheet("background-color: #2ecc71; border-radius: 5px; border: none;")
            elif idx == self.active_step_index:
                node.setStyleSheet("background-color: #3498db; border-radius: 5px; border: 1px solid #2980b9;")
            else:
                node.setStyleSheet("background-color: #cbd5e1; border-radius: 5px; border: none;")
                
        self.update()

    def paintEvent(self, event):
        """Draws native pixel-perfect tracking line connections directly under the dots."""
        super().paintEvent(event)
        if len(self.step_nodes) < 2:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for i in range(self.num_stages - 1):
            pt_left = self.step_nodes[i].geometry().center() + self.track_container.pos()
            pt_right = self.step_nodes[i+1].geometry().center() + self.track_container.pos()

            if i < self.active_step_index:
                line_color = QColor("#2ecc71")
            else:
                line_color = QColor("#cbd5e1")

            pen = QPen(line_color, 2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(pt_left, pt_right)

    def set_collapsed_mode(self, collapsed: bool):
        if collapsed:
            self.title_container.hide()
            self.delete_button.hide()
            self.track_container.hide()
            self.setFixedSize(50, 50)
            self.main_layout.setContentsMargins(0, 0, 0, 0)
        else:
            self.title_container.show()
            self.delete_button.show()
            self.track_container.show()
            self.setFixedSize(280, 105)
            self.main_layout.setContentsMargins(14, 12, 14, 12)

    def confirm_and_delete_subdirectory(self):
        confirm_box = QMessageBox(self)
        confirm_box.setIcon(QMessageBox.Icon.Warning)
        confirm_box.setWindowTitle("Delete Order Directory")
        confirm_box.setText(f"Are you sure you want to completely delete order folder '{self.order_id}'?")
        
        yes_button = confirm_box.addButton("Delete Permanently", QMessageBox.ButtonRole.YesRole)
        cancel_button = confirm_box.addButton(QMessageBox.StandardButton.Cancel)
        confirm_box.setDefaultButton(cancel_button)
        confirm_box.exec()

        if confirm_box.clickedButton() == yes_button:
            try:
                if self.directory_path and os.path.exists(self.directory_path):
                    shutil.rmtree(self.directory_path)
                self.close()
                self.deleteLater()
            except Exception as e:
                pass