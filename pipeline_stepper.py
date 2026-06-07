from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush

class ProgressCircleNode(QWidget):
    """Custom canvas-drawn circle that turns into an arc progress wheel or a checkmark."""
    clicked = pyqtSignal(int)

    def __init__(self, step_index):
        super().__init__()
        self.step_index = step_index
        self.setFixedSize(26, 26)
        self.status = "idle"  # idle, active, completed
        self.progress_value = 0.0  # 0.0 to 1.0 (for the sweeping arc)

    def set_status(self, status, progress=0.0):
        self.status = status
        self.progress_value = progress
        self.update()  # Triggers paintEvent redraw

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.step_index)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = QRectF(2, 2, self.width() - 4, self.height() - 4)

        if self.status == "idle":
            # Dull gray unreached circle
            painter.setPen(QPen(QColor("#7f8c8d"), 2))
            painter.setBrush(QBrush(QColor("#34495e")))
            painter.drawEllipse(rect)
            
        elif self.status == "active":
            # Gray tracking background track
            painter.setPen(QPen(QColor("#34495e"), 2))
            painter.setBrush(QBrush(QColor("#1a252f")))
            painter.drawEllipse(rect)
            
            # Sweeping progress arc ring
            pen = QPen(QColor("#3498db"), 3)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            # Calculations mapped out: startAngle is top (90 deg), spanAngle sweeps backward
            start_angle = 90 * 16
            span_angle = int(-self.progress_value * 360 * 16)
            painter.drawArc(rect, start_angle, span_angle)
            
        elif self.status == "completed":
            # Solid accent green bubble
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#2ecc71")))
            painter.drawEllipse(rect)
            
            # White minimal vector checkmark layout
            pen = QPen(QColor("#ffffff"), 2.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            # Canvas drawing vector paths relative to widget bounds
            painter.drawLine(int(self.width()*0.32), int(self.height()*0.5), int(self.width()*0.46), int(self.height()*0.65))
            painter.drawLine(int(self.width()*0.46), int(self.height()*0.65), int(self.width()*0.72), int(self.height()*0.35))


class PipelineStepperWidget(QWidget):
    """Horizontal navigation bar managing multi-step text alignments and connector links."""
    stage_selected = pyqtSignal(int)

    def __init__(self, stages_meta):
        super().__init__()
        self.stages = stages_meta
        self.nodes = []
        self.lines = []
        self.current_active_idx = 0
        self.init_ui()

    def init_ui(self):
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(10, 5, 10, 5)
        self.main_layout.setSpacing(0)

        for i, stage_name in enumerate(self.stages):
            # Vertical package grouping: Stage #, Circle Node, Stage Label Text
            step_container = QWidget()
            step_layout = QVBoxLayout(step_container)
            step_layout.setContentsMargins(0, 0, 0, 0)
            step_layout.setSpacing(4)
            step_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # Above: Smaller font Stage #
            num_label = QLabel(f"Stage {i+1}")
            num_label.setStyleSheet("color: #7f8c8d; font-size: 10px; font-weight: bold;")
            num_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            step_layout.addWidget(num_label)

            # Center: Interaction Target Circle
            node = ProgressCircleNode(i)
            node.clicked.connect(self.stage_selected.emit)
            step_layout.addWidget(node)
            self.nodes.append(node)

            # Below: Full Stage Name String
            name_label = QLabel(stage_name)
            name_label.setStyleSheet("color: black; font-size: 11px; font-weight: 500;")
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            step_layout.addWidget(name_label)

            self.main_layout.addWidget(step_container)

            # Add horizontal bridging links between container blocks
            if i < len(self.stages) - 1:
                line_wrapper = QWidget()
                line_box = QVBoxLayout(line_wrapper)
                line_box.setContentsMargins(10, 20, 10, 0) # Offset to align link paths centrally
                
                line = QFrame()
                line.setFixedHeight(2)
                line.setStyleSheet("background-color: #34495e;")
                line_box.addWidget(line)
                
                self.main_layout.addWidget(line_wrapper, stretch=1)
                self.lines.append(line)

        self.update_step_visuals(0, 0.0)

    def update_step_visuals(self, target_idx, active_progress=0.0):
        """Drives the status assignments down to specific connection pipes and canvas nodes."""
        self.current_active_idx = target_idx
        for i in range(len(self.nodes)):
            if i < target_idx:
                self.nodes[i].set_status("completed")
                if i < len(self.lines):
                    self.lines[i].setStyleSheet("background-color: #2ecc71;")
            elif i == target_idx:
                self.nodes[i].set_status("active", active_progress)
                if i < len(self.lines):
                    self.lines[i].setStyleSheet("background-color: #34495e;")
            else:
                self.nodes[i].set_status("idle")
                if i < len(self.lines):
                    self.lines[i].setStyleSheet("background-color: #34495e;")