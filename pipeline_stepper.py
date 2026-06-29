import os
from PyQt6.QtWidgets import QWidget, QGridLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QFontDatabase, QFont, QPainter, QPen, QColor

class ProgressCircleNode(QLabel):
    """Sleek UI Node driven by Material Symbols font characters."""
    clicked = pyqtSignal(int)

    def __init__(self, step_index, glyph_char, font_family):
        super().__init__()
        self.step_index = step_index
        self.glyph_char = glyph_char
        
        self.setFixedSize(32, 32)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContentsMargins(0, 0, 0, 0)
        
        self.setFont(QFont(font_family, 14))
        self.setText(self.glyph_char)
        self.status = "idle"

    def set_status(self, status):
        self.status = status
        self.update_visuals()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.step_index)

    def update_visuals(self):
        if self.status == "idle":
            self.setStyleSheet("""
                background-color: #34495e; 
                color: #7f8c8d; 
                border-radius: 16px; 
                border: 2px solid #7f8c8d;
            """)
        elif self.status == "active":
            self.setStyleSheet("""
                background-color: #fac115; 
                color: #3498db; 
                border-radius: 16px; 
                border: 2px solid #3498db;
            """)
        elif self.status == "completed":
            self.setStyleSheet("""
                background-color: #166534; 
                color: #dcfce7; 
                border-radius: 16px; 
                border: 2px solid #166534;
            """)


class PipelineStepperWidget(QWidget):
    """Horizontal navigation bar managing multi-step text alignments with a canvas-drawn tracking line."""
    stage_selected = pyqtSignal(int)

    def __init__(self, stages_meta, glyph_map):
        super().__init__()
        self.stages = stages_meta
        self.glyph_map = glyph_map
        self.nodes = []
        self.current_active_idx = 0
        
        # Load custom icon font
        font_path = "fonts/MaterialSymbolsRounded[FILL,GRAD,opsz,wght].ttf"
        font_id = QFontDatabase.addApplicationFont(font_path)
        font_families = QFontDatabase.applicationFontFamilies(font_id)
        self.font_family = font_families[0] if font_families else "Material Symbols Rounded"

        self.init_ui()

    def init_ui(self):
        self.grid_layout = QGridLayout(self)
        self.grid_layout.setContentsMargins(20, 10, 20, 10)
        self.grid_layout.setSpacing(0)
        self.grid_layout.setVerticalSpacing(8)

        num_stages = len(self.stages)

        for i, stage_name in enumerate(self.stages):
            col_idx = i * 2

            # --- Row 0: Step / Stage Numbers ---
            num_label = QLabel(f"Step {i+1}")
            num_label.setStyleSheet("color: #0F172A; font-size: 10px; font-weight: bold;")
            num_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(num_label, 0, col_idx, Qt.AlignmentFlag.AlignCenter)

            # --- Row 1: Material Design Graphic Nodes ---
            glyph = self.glyph_map.get(i, "?")
            node = ProgressCircleNode(i, glyph, self.font_family)
            node.clicked.connect(self.stage_selected.emit)
            
            self.grid_layout.addWidget(node, 1, col_idx, Qt.AlignmentFlag.AlignCenter)
            self.nodes.append(node)

            # --- Row 2: Text Descriptions ---
            name_label = QLabel(stage_name)
            name_label.setStyleSheet("color: black; font-size: 11px; font-weight: 500;")
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_label.setWordWrap(True)
            name_label.setFixedWidth(100)
            self.grid_layout.addWidget(name_label, 2, col_idx, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

            # Distribute column space fluidly between nodes
            if i < num_stages - 1:
                self.grid_layout.setColumnStretch(col_idx + 1, 1)

        self.update_step_visuals(0)

    def update_step_visuals(self, target_idx):
        """Updates states of nodes and flags a repaint for the background lines."""
        self.current_active_idx = target_idx
        for i in range(len(self.nodes)):
            if i < target_idx:
                self.nodes[i].set_status("completed")
            elif i == target_idx:
                self.nodes[i].set_status("active")
            else:
                self.nodes[i].set_status("idle")
        
        self.update() # Triggers paintEvent to redraw the center lines perfectly

    def paintEvent(self, event):
        """Draws pixel-perfect connection line tracking segments natively from center to center."""
        super().paintEvent(event)
        
        if len(self.nodes) < 2:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw the line segments connecting the centers of the nodes
        for i in range(len(self.nodes) - 1):
            node_left = self.nodes[i]
            node_right = self.nodes[i+1]

            # Calculate geometric centers relative to PipelineStepperWidget coordinates
            center_left = node_left.geometry().center()
            center_right = node_right.geometry().center()

            # Determine color state of this line segment
            if i < self.current_active_idx:
                line_color = QColor("#166534")  # Completed (Green)
            else:
                line_color = QColor("#34495e")  # Unreached (Dark Grey)

            pen = QPen(line_color, 3)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            
            # Draw vector line segment
            painter.drawLine(center_left, center_right)