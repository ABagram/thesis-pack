import os
import json
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame, QStackedWidget
from pipeline_stepper import PipelineStepperWidget

# Define your pipeline array as a single source of truth
PRODUCTION_STAGES = [
    "Order Capture", "Item Count", "Item Identification",
    "Minimum Box Computation", "Parametric Dieline Generation",
    "G-Code Generation", "G-Code Upload", "Dieline Done"
]

# Map your index steps to specific unicode character tags within the TTF asset
GLYPH_MAP = {
    0: "\ue412", # photo_camera
    1: "\ueac7", # numbers
    2: "\ue43f", # image_search
    3: "\uf569", # package_2
    4: "\ueb14", # orders
    5: "\ueb8e", # terminal
    6: "\ue2c3", # cloud_upload
    7: "\ue86c"  # check_circle
}

# Unified directory manifest parsing lookup map
STAGE_INDEX_MAP = {
    "snapshot_pending": 0, "retake": 0,
    "counting": 1,         "count_failed": 1,
    "identifying": 2,      "dimensioning": 2,
    "bin_packing": 3,
    "dieline_generation": 4,
    "gcode_generation": 5,
    "gcode_upload": 6,
    "completed": 7
}

class MainContentWidget(QWidget):
    hardware_trigger_clicked = pyqtSignal()
    order_state_updated = pyqtSignal(str, dict)  # (order_id, state_data)

    def __init__(self):
        super().__init__()
        self.mock_progress_index = 0
        self.current_order_id = None
        self.current_order_directory = None
        self.sim_timer = QTimer(self)
        self.sim_timer.timeout.connect(self._advance_mock_pipeline)
        self.init_ui()

    def init_ui(self):
        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(15, 15, 15, 15)
        self.content_layout.setSpacing(15)
        
        # 1. Physical Loop Emulator Viewport controls
        self.mock_hw_frame = QFrame()
        self.mock_hw_frame.setStyleSheet("background-color: #1a252f; border: 1px dashed #34495e; border-radius: 6px;")
        self.hw_layout = QVBoxLayout(self.mock_hw_frame)
        
        self.hw_title = QLabel("📡 Physical Hardware Loop Emulator")
        self.hw_title.setStyleSheet("color: #ecf0f1; font-weight: bold;")
        self.hw_layout.addWidget(self.hw_title)
        
        btn_layout = QHBoxLayout()
        self.btn_order_esp = QPushButton("New Order Trigger")
        self.btn_order_esp.setStyleSheet("background-color: #e74c3c; color: white; padding: 10px; font-weight: bold; border-radius: 4px;")
        
        self.btn_simulate_esp = QPushButton("Start Cycle Monitor")
        self.btn_simulate_esp.setStyleSheet("background-color: #2ecc71; color: white; padding: 10px; font-weight: bold; border-radius: 4px;")
        
        btn_layout.addWidget(self.btn_order_esp)
        btn_layout.addWidget(self.btn_simulate_esp)
        self.hw_layout.addLayout(btn_layout)
        self.content_layout.addWidget(self.mock_hw_frame)

        # 2. Dynamic Component Stepper Instantiation
        self.pipeline_stepper = PipelineStepperWidget(PRODUCTION_STAGES, GLYPH_MAP)
        self.pipeline_stepper.stage_selected.connect(self.handle_stage_navigation)
        self.content_layout.addWidget(self.pipeline_stepper)

        # 3. Stacked Containers for Viewports
        self.tab_stack = QStackedWidget()
        self.tab_stack.setStyleSheet("background-color: #2c3e50; border-radius: 6px; border: 1px solid #34495e;")
        
        # Generate view panels dynamically to match your step array lengths
        for stage in PRODUCTION_STAGES:
            view = QLabel(f"<h1>{stage}</h1><p>Algorithmic logs and execution paths for node context tracking.</p>")
            view.setAlignment(Qt.AlignmentFlag.AlignCenter)
            view.setStyleSheet("color: white; padding: 20px;")
            self.tab_stack.addWidget(view)
            
        self.content_layout.addWidget(self.tab_stack)

        self.display_label = QLabel("Select an automated order node on the left to review metrics.")
        self.display_label.setStyleSheet("font-size: 13px; color: #7f8c8d;")
        self.content_layout.addWidget(self.display_label)

        # Event connections
        self.btn_simulate_esp.clicked.connect(self.start_mock_pipeline_animation)
        self.btn_order_esp.clicked.connect(self.hardware_trigger_clicked.emit)

    def handle_stage_navigation(self, index):
        self.tab_stack.setCurrentIndex(index)

    def update_display_details(self, order_id, active_directory):
        self.current_order_id = order_id
        self.current_order_directory = active_directory
        order_path = os.path.join(active_directory, order_id)
        order_stage = "snapshot_pending"
        
        if os.path.exists(os.path.join(order_path, "order_manifest.json")):
            try:
                with open(os.path.join(order_path, "order_manifest.json"), 'r') as f:
                    order_stage = json.load(f).get("stage", "snapshot_pending")
            except Exception:
                pass

        active_step = STAGE_INDEX_MAP.get(order_stage, 0)
        self.sim_timer.stop() 
        
        self.pipeline_stepper.update_step_visuals(active_step)
        self.tab_stack.setCurrentIndex(active_step)
        self.display_label.setText(f"<h2>In view: {order_id.replace('_', ' ').title()}</h2><hr>")

    def start_mock_pipeline_animation(self):
        self.mock_progress_index = 0
        self.tab_stack.setCurrentIndex(0)
        self.pipeline_stepper.update_step_visuals(self.mock_progress_index)
        self.sim_timer.start(1200) # Advances stages sequentially every 1.2s

    def _advance_mock_pipeline(self):
        self.mock_progress_index += 1
        max_stages = len(self.pipeline_stepper.stages)
        
        if self.mock_progress_index >= max_stages:
            self.sim_timer.stop()
            self.pipeline_stepper.update_step_visuals(max_stages) # Complete all nodes
            return
            
        self.tab_stack.setCurrentIndex(self.mock_progress_index)
        self.pipeline_stepper.update_step_visuals(self.mock_progress_index)
        
        # Sync sidebar and update manifest
        if self.current_order_id and self.current_order_directory:
            # Create reverse mapping from index to stage name
            reverse_stage_map = {v: k for k, v in STAGE_INDEX_MAP.items()}
            stage_name = reverse_stage_map.get(self.mock_progress_index, "snapshot_pending")
            
            # Update manifest file
            order_path = os.path.join(self.current_order_directory, self.current_order_id)
            manifest_path = os.path.join(order_path, "order_manifest.json")
            try:
                if os.path.exists(manifest_path):
                    with open(manifest_path, 'r') as f:
                        manifest = json.load(f)
                    manifest["stage"] = stage_name
                    with open(manifest_path, 'w') as f:
                        json.dump(manifest, f, indent=4)
                    
                    # Emit signal to sync sidebar
                    self.order_state_updated.emit(self.current_order_id, manifest)
            except Exception:
                pass