import os
import shutil
from PyQt6.QtWidgets import (QHBoxLayout, QVBoxLayout, QPushButton, 
                             QLabel, QFrame, QSizePolicy, QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontDatabase, QFont

class OrderItemWidget(QPushButton):
    """A custom widget representing an individual order subdirectory with an integrated vertical pipeline tracker."""
    def __init__(self, order_id, status_data, directory_path="", parent=None):
        super().__init__(parent)
        
        # 1. Isolate this specific widget and its children from global style.qss rules
        self.setObjectName("MainOrderItemWidget")
        
        self.setFixedWidth(260) 
        self.setFixedHeight(220) # Expanded height from 100 to comfortably fit vertical steps

        # 2. Safely load font file (Handles both Outlined and Rounded weights seamlessly)
        font_id = QFontDatabase.addApplicationFont("MaterialSymbolsRounded[FILL,GRAD,opsz,wght].ttf")
        if font_id == -1:
            print("[WARNING] Material Symbols Font failed to load! Check your file path.")
        
        font_families = QFontDatabase.applicationFontFamilies(font_id)
        font_family = font_families[0] if font_families else "Material Symbols Outlined"
        
        self.order_id = order_id
        self.directory_path = directory_path 
        
        # Base Widget Layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(14, 12, 14, 12)
        self.main_layout.setSpacing(10)

        # =====================================================================
        # TOP ROW: Status Indicator & Order Title
        # =====================================================================
        self.header_layout = QHBoxLayout()
        self.header_layout.setSpacing(8)
        
        # Status Dot
        self.status_indicator = QFrame()
        self.status_indicator.setFixedSize(10, 10)
        self.header_layout.addWidget(self.status_indicator)
        
        # Title Label
        self.title_label = QLabel(order_id.replace("_", " ").title())
        self.title_label.setObjectName("WidgetTitleLabel")
        self.header_layout.addWidget(self.title_label)
        self.header_layout.addStretch()
        
        self.main_layout.addLayout(self.header_layout)

        # =====================================================================
        # MIDDLE ROW: Active Status Badge & Action Buttons
        # =====================================================================
        self.badge_and_action_layout = QHBoxLayout()
        
        # Active Status Badge
        self.badge_frame = QFrame()
        self.badge_frame.setObjectName('badge')
        self.badge_layout = QHBoxLayout(self.badge_frame)
        self.badge_layout.setContentsMargins(8, 4, 8, 4)
        
        self.badge_text = QLabel("Initializing...")
        self.badge_layout.addWidget(self.badge_text)
        self.badge_and_action_layout.addWidget(self.badge_frame)
        self.badge_and_action_layout.addStretch()
        
        # Action Button: Delete Forever (Styled dynamically using safe explicit ID targeting)
        self.delete_button = QPushButton("delete_forever", self) 
        self.delete_button.setObjectName("WidgetDeleteButton")
        self.delete_button.setToolTip("Delete Order Permanently")
        self.delete_button.setFixedSize(28, 28)
        self.delete_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.delete_button.clicked.connect(self.confirm_and_delete_subdirectory)
        self.badge_and_action_layout.addWidget(self.delete_button)
        
        self.main_layout.addLayout(self.badge_and_action_layout)

        # =====================================================================
        # BOTTOM SECTION: Downward/Vertical Progress Pipeline
        # =====================================================================
        self.pipeline_container = QFrame()
        self.pipeline_container.setObjectName("PipelineContainer")
        self.pipeline_layout = QVBoxLayout(self.pipeline_container)
        self.pipeline_layout.setContentsMargins(4, 4, 4, 4)
        self.pipeline_layout.setSpacing(0) # Controlled manually via lines
        
        self.step_nodes = []
        self.step_lines = []
        self.step_labels = []
        
        # Descriptions mapping perfectly to milestone indices
        step_descriptions = [
            "Photo Capture & Verification",
            "Image Segmentation & Classification",
            "3D Bin Packing Optimization",
            "G-Code File Compilation"
        ]
        
        for i in range(4):
            step_row = QHBoxLayout()
            step_row.setSpacing(10)
            
            # Node Dot indicator
            node = QLabel(str(i+1))
            node.setFixedSize(18, 18)
            node.setAlignment(Qt.AlignmentFlag.AlignCenter)
            step_row.addWidget(node)
            self.step_nodes.append(node)
            
            # Descriptive text beside node
            lbl = QLabel(step_descriptions[i])
            lbl.setObjectName(f"StepLabel_{i}")
            step_row.addWidget(lbl)
            self.step_labels.append(lbl)
            step_row.addStretch()
            
            self.pipeline_layout.addLayout(step_row)
            
            if i < 3: # Vertical connector track lines between nodes
                line_row = QHBoxLayout()
                line_row.setSpacing(0)
                
                # Container to mimic structural indentation alignment
                line_spacer = QFrame()
                line_spacer.setFixedWidth(8) # Center line to an 18px node width
                
                line = QFrame()
                line.setFixedWidth(2)
                line.setFixedHeight(12)
                
                line_row.addWidget(line_spacer)
                line_row.addWidget(line)
                line_row.addStretch()
                
                self.pipeline_layout.addLayout(line_row)
                self.step_lines.append(line)
                
        self.main_layout.addWidget(self.pipeline_container)
        
        # =====================================================================
        # SPECIFIC COMPONENT STYLESHEETS (Immune to style.qss cascade issues)
        # =====================================================================
        self.delete_button.setStyleSheet(f"""
            QPushButton#WidgetDeleteButton {{
                background-color: transparent !important;
                border: none !important;
                font-family: "{font_family}" !important;
                font-size: 18px !important; 
                color: #181818 !important;
                text-align: center !important;
                padding: 0px !important;
            }}
            QPushButton#WidgetDeleteButton:hover {{
                background-color: #e74c3c !important;
                border-radius: 4px !important;
            }}
        """)
        
        self.setStyleSheet(f"""
            QPushButton#MainOrderItemWidget {{ 
                background-color: #ffffff; 
                border-radius: 0.4em; 
                text-align: left;
            }} 
            QPushButton#MainOrderItemWidget:hover {{ 
                background-color: #34495e; 
            }}
            QLabel#WidgetTitleLabel {{
                color: #181818; 
                font-size: 13px; 
                border: none;
                background: transparent;
            }}
        """)

        self.update_state(status_data)

    def update_state(self, data):
        """Maps files and pipeline tracking milestones onto the active UI elements."""
        state = data.get("stage", "snapshot_pending")
        current_step = data.get("current_item", 0)
        total_steps = data.get("total_items", 0)
        
        # State Map: (base_hex_color, label_text, active_step_index)
        # Using a single base color allows us to keep the text and border uniformly colored,
        # while using a lighter/tinted version of that same color for the background.
        state_map = {
            "snapshot_pending": ("#7f8c8d", "📷 WAITING FOR CAPTURE", 1),
            "validating":       ("#f1c40f", "🔍 CHECKING SPACING", 1),
            "retake":           ("#e74c3c", "⚠️ PHOTO RETAKE REQUIRED", 1),
            "segmenting":       ("#9b59b6", "🧬 SEGMENTING IMAGES", 2),
            "classifying":      ("#3498db", f"🏷️ CLASSIFYING ({current_step}/{total_steps})", 2),
            "dimensioning":     ("#e67e22", f"📏 CAM-DIMENSION ({current_step}/{total_steps})", 2),
            "bin_packing":      ("#34495e", "📦 3D BIN PACKING", 3), 
            "gcode_ready":      ("#2ecc71", "⚙️ GCODE READY", 4)
        }

        base_color, label_text, active_step_index = state_map.get(
            state, ("#7f8c8d", "UNKNOWN", 1)
        )

        # ADJUST THIS PLACEHOLDER BACKGROUND OPACITY AS NEEDED
        # 0.15 represents 15% opacity of the base color to create that soft pastel background effect
        bg_opacity = 0.15 

        # Convert hex to RGBA string for the background style
        # Removes the '#' and splits the hex string into integer R, G, B channels
        hex_val = base_color.lstrip('#')
        r, g, b = tuple(int(hex_val[i:i+2], 16) for i in (0, 2, 4))
        rgba_bg_color = f"rgba({r}, {g}, {b}, {bg_opacity})"

        # Update text badge elements
        self.status_indicator.setStyleSheet(f"background-color: {base_color}; border-radius: 5px; border: none;")
        self.badge_text.setText(label_text)
        
        # Text inherits the strong, solid base color
        self.badge_text.setStyleSheet(f"""
            color: {base_color}; 
            font-size: 10px; 
            font-weight: bold; 
            border: none; 
            background: transparent; 
            padding: 0px;
        """)
        
        # Border inherits the base color, background uses the tinted RGBA variant
        self.badge_frame.setStyleSheet(f"""
            #badge {{ 
                background-color: {rgba_bg_color};
                border: 1px solid {base_color}; 
                border-radius: 12px; 
            }}
        """)

        # Dynamically process vertical pipeline node highlights
        for idx in range(4):
            node = self.step_nodes[idx]
            text_lbl = self.step_labels[idx]
            
            if idx < active_step_index:
                # Milestone Completed / Highlighting Active
                node.setStyleSheet("background-color: #2ecc71; color: #181818; border-radius: 9px; font-size: 9px; border: none;")
                text_lbl.setStyleSheet("color: #181818; font-size: 11px; border: none; background: transparent;")
                if idx < 3:
                    self.step_lines[idx].setStyleSheet("background-color: #2ecc71; border: none;")
            elif idx == active_step_index:
                # Current Step Processing glow
                node.setStyleSheet("background-color: #3498db; color: #181818; border-radius: 9px; font-size: 9px; border: none;")
                text_lbl.setStyleSheet("color: #3498db; font-size: 11px; border: none; background: transparent;")
                if idx < 3:
                    self.step_lines[idx].setStyleSheet("background-color: #34495e; border: none;")
            else:
                # Inactive / Unreached elements
                node.setStyleSheet("background-color: #34495e; color: #7f8c8d; border-radius: 9px; font-size: 9px; border: none;")
                text_lbl.setStyleSheet("color: #7f8c8d; font-size: 11px; font-weight: normal; border: none; background: transparent;")
                if idx < 3:
                    self.step_lines[idx].setStyleSheet("background-color: #34495e; border: none;")
                    
    def set_collapsed_mode(self, collapsed: bool):
        if collapsed:
            self.title_label.hide()
            self.badge_frame.hide()
            self.delete_button.hide()
            self.pipeline_container.hide()
            self.main_layout.setContentsMargins(20, 12, 20, 12)
        else:
            self.title_label.show()
            self.badge_frame.show()
            self.delete_button.show()
            self.pipeline_container.show()
            self.main_layout.setContentsMargins(14, 12, 14, 12)

    def confirm_and_delete_subdirectory(self):
        confirm_box = QMessageBox(self)
        confirm_box.setIcon(QMessageBox.Icon.Warning)
        confirm_box.setWindowTitle("Delete Order Directory")
        confirm_box.setText(f"Are you sure you want to completely delete order folder '{self.order_id}'?")
        confirm_box.setInformativeText("This will permanently scrub local files. This action cannot be undone.")
        
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
                error_box = QMessageBox(self)
                error_box.setIcon(QMessageBox.Icon.Critical)
                error_box.setText("Failed to completely remove subdirectory.")
                error_box.setInformativeText(str(e))
                error_box.exec()