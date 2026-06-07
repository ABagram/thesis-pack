import sys
import os
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QFrame, QStackedWidget)
from pipeline_stepper import PipelineStepperWidget

class MainContentWidget(QWidget):
    """Handles the hardware loop emulation and workspace item metric visualization."""
    hardware_trigger_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.init_ui()
        
        # MOCK SYSTEM: Setting up a simulator ticker to show off the arc loading wheel wheel
        self.mock_progress = 0.0
        self.mock_stage = 0
        self.sim_timer = QTimer(self)
        self.sim_timer.timeout.connect(self._advance_mock_pipeline)

    def init_ui(self):
        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(15, 15, 15, 15)
        self.content_layout.setSpacing(15)
        
        # 1. HARDWARE EMULATION COMPONENT (Top Box)
        self.mock_hw_frame = QFrame()
        self.mock_hw_frame.setStyleSheet("background-color: #1a252f; border: 1px dashed #34495e; border-radius: 6px;")
        self.hw_layout = QVBoxLayout(self.mock_hw_frame)
        
        self.hw_title = QLabel("📡 Physical Hardware Loop Emulator")
        self.hw_title.setStyleSheet("color: #ecf0f1; font-weight: bold;")
        self.hw_layout.addWidget(self.hw_title)
        
        self.btn_simulate_esp = QPushButton("🔴 New Order (Simulate ESP Signal & Cycle Progress)")
        self.btn_simulate_esp.setStyleSheet("background-color: #e74c3c; color: white; padding: 10px; font-weight: bold; border-radius: 4px;")
        self.hw_layout.addWidget(self.btn_simulate_esp)
        self.content_layout.addWidget(self.mock_hw_frame)

        # 2. THE MULTI-STEP PROGRESS STEPPER NAVIGATION BAR
        stages = [
            "Order Capture & Verification",
            "3D Bin Packing",
            "Parametric Dieline & G-Code"
        ]
        self.pipeline_stepper = PipelineStepperWidget(stages)
        # Clicking a circle directly signals the stacked widget to change visible index views
        self.pipeline_stepper.stage_selected.connect(self.handle_stage_navigation)
        self.content_layout.addWidget(self.pipeline_stepper)

        # 3. CONTAINER TABS VIEWPORTS (QStackedWidget)
        self.tab_stack = QStackedWidget()
        self.tab_stack.setStyleSheet("background-color: #2c3e50; border-radius: 6px; border: 1px solid #34495e;")
        
        # Generate placeholder cards matching structural steps
        self.tab1_view = QLabel("<h1>Stage 1 View</h1><p>Content for Verification details...</p>")
        self.tab2_view = QLabel("<h1>Stage 2 View</h1><p>Content for 3D Bin Packing algorithms...</p>")
        self.tab3_view = QLabel("<h1>Stage 3 View</h1><p>Content for CNC Dieline parameters and profiles...</p>")
        
        for view in [self.tab1_view, self.tab2_view, self.tab3_view]:
            view.setAlignment(Qt.AlignmentFlag.AlignCenter)
            view.setStyleSheet("color: white; padding: 20px;")
            self.tab_stack.addWidget(view)
            
        self.content_layout.addWidget(self.tab_stack)

        # Bottom Default Fallback Text Label
        self.display_label = QLabel("Select an automated order node on the left to review metrics.")
        self.display_label.setStyleSheet("font-size: 13px; color: #7f8c8d;")
        self.content_layout.addWidget(self.display_label)

        # Connections
        self.btn_simulate_esp.clicked.connect(self.start_mock_pipeline_animation)
        self.btn_simulate_esp.clicked.connect(self.hardware_trigger_clicked.emit)

    def handle_stage_navigation(self, index):
        """Changes target layouts based on node selection clicks."""
        self.tab_stack.setCurrentIndex(index)
        print(f"Switched container tab context viewport view to: Stage Index {index + 1}")

    def update_display_details(self, order_id, active_directory):
        order_path = os.path.join(active_directory, order_id)
        
        has_jpg = os.path.exists(os.path.join(order_path, "cv_capture.jpg"))
        has_gcode = os.path.exists(os.path.join(order_path, "box_blank.gcode"))
        has_manifest = os.path.exists(os.path.join(order_path, "order_manifest.json"))
        
        info_html = f"<h2>Workspace Profile: {order_id.replace('_', ' ').title()}</h2><hr>"
        info_html += f"<p><b>Asset Manifest Tree Checklist:</b></p>"
        info_html += f"<p>{'✅' if has_jpg else '❌'} <code>cv_capture.jpg</code> (Camera Snapshot)</p>"
        info_html += f"<p>{'✅' if has_manifest else '❌'} <code>order_manifest.json</code> (Sizing Metadata)</p>"
        info_html += f"<p>{'✅' if has_gcode else '❌'} <code>box_blank.gcode</code> (CNC Output)</p>"
        
        self.display_label.setText(info_html)

    # =========================================================================
    # PIPELINE PROGRESS RUNTIME MOCK SIMULATOR RUNNERS
    # =========================================================================
    def start_mock_pipeline_animation(self):
        self.mock_progress = 0.0
        self.mock_stage = 0
        self.tab_stack.setCurrentIndex(0)
        self.pipeline_stepper.update_step_visuals(self.mock_stage, self.mock_progress)
        self.sim_timer.start(50) # Cycle update intervals every 50ms

    def _advance_mock_pipeline(self):
        self.mock_progress += 0.02
        if self.mock_progress >= 1.0:
            self.mock_progress = 0.0
            self.mock_stage += 1
            if self.mock_stage >= 3:
                self.sim_timer.stop()
                # Light up all step elements complete
                self.pipeline_stepper.update_step_visuals(3, 0.0)
                return
            self.tab_stack.setCurrentIndex(self.mock_stage)
            
        self.pipeline_stepper.update_step_visuals(self.mock_stage, self.mock_progress)