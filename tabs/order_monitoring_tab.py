import json
import os

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QStackedWidget, QVBoxLayout, QWidget

from order_nav_sidebar import OrderQueue
from pipeline_stepper import PipelineStepperWidget

PRODUCTION_STAGES = [
    "Order Capture", "Item Count", "Item Identification",
    "Minimum Box Computation", "Parametric Dieline Generation",
    "G-Code Generation", "G-Code Upload", "Dieline Done"
]

GLYPH_MAP = {
    0: "\ue412", 1: "\ueac7", 2: "\ue43f", 3: "\uf569",
    4: "\ueb14", 5: "\ueb8e", 6: "\ue2c3", 7: "\ue86c"
}

STAGE_INDEX_MAP = {
    "snapshot_pending": 0, "order_capture": 0, "snapshot_complete": 0, "retake": 0,
    "counting": 1, "count_failed": 1, "identifying": 2,
    "dimensioning": 2, "bin_packing": 3, "dieline_generation": 4,
    "gcode_generation": 5, "gcode_upload": 6, "completed": 7
}


class OrderMonitoringTab(QWidget):
    order_state_updated = pyqtSignal(str, dict)

    def __init__(self, default_batch_directory, order_queue_position="right", parent=None):
        super().__init__(parent)
        self.current_order_id = None
        self.current_order_directory = None
        self.mock_progress_index = 0
        self.order_queue_position = order_queue_position
        self.sim_timer = QTimer(self)
        self.sim_timer.timeout.connect(self._advance_mock_pipeline)
        self.capture_refresh_timer = QTimer(self)
        self.capture_refresh_timer.timeout.connect(self.refresh_current_order)
        self.capture_refresh_timer.start(1000)
        self._build_ui(default_batch_directory)

    def handle_order_created(self, order_id, order_path):
        self.current_order_id = order_id
        self.current_order_directory = os.path.dirname(order_path)
        self.display_label.setText(
            f"<h2>Order Capture in progress: {order_id}</h2><hr>"
        )
        self.tab_stack.setCurrentIndex(0)
        self.pipeline_stepper.update_step_visuals(0)


    def handle_order_cancelled(self, order_id):
        """
        Clear the currently displayed order after the Master
        reports that the order was cancelled.
        """
        if self.current_order_id != order_id:
            return

        self.current_order_id = None
        self.current_order_directory = None

        self.sim_timer.stop()

        self.display_label.setText(
            "Order cancelled. Ready for the next order."
        )

        self.pipeline_stepper.update_step_visuals(0)
        self.tab_stack.setCurrentIndex(0)

        # Clear captured photos and restore waiting labels.
        for role, label in self.capture_photo_labels:
            label.clear()
            label.setText(f"Waiting for {role} camera")
            
    def refresh_current_order(self):
        if not self.current_order_id or not self.current_order_directory:
            return
        manifest_path = os.path.join(
            self.current_order_directory, self.current_order_id, "order_manifest.json"
        )
        try:
            with open(manifest_path, "r") as file:
                manifest = json.load(file)
        except (OSError, json.JSONDecodeError):
            return
        self.refresh_capture_photos(self.current_order_id, self.current_order_directory)
        active_step = STAGE_INDEX_MAP.get(manifest.get("stage"), 0)
        self.pipeline_stepper.update_step_visuals(active_step)
        self.tab_stack.setCurrentIndex(active_step)

    def _build_ui(self, default_batch_directory):
        queue_is_horizontal = self.order_queue_position in {"top", "bottom"}
        layout = QVBoxLayout(self) if queue_is_horizontal else QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)
        self.order_queue = OrderQueue(default_batch_directory, position=self.order_queue_position)
        pipeline_container = QWidget()
        pipeline_layout = QVBoxLayout(pipeline_container)
        pipeline_layout.setContentsMargins(0, 0, 0, 0)
        pipeline_layout.setSpacing(15)
        self.pipeline_stepper = PipelineStepperWidget(PRODUCTION_STAGES, GLYPH_MAP)
        self.pipeline_stepper.stage_selected.connect(self.handle_stage_navigation)
        pipeline_layout.addWidget(self.pipeline_stepper)
        self.tab_stack = QStackedWidget()
        self.tab_stack.setStyleSheet(
            "background-color: #2c3e50; border-radius: 6px; border: 1px solid #34495e;"
        )
        self.capture_photo_labels = []
        for index, stage in enumerate(PRODUCTION_STAGES):
            if index == 0:
                view = QWidget()
                capture_layout = QVBoxLayout(view)
                capture_title = QLabel("<h1>Order Capture</h1>")
                capture_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
                capture_layout.addWidget(capture_title)
                photo_row = QHBoxLayout()
                for role in ("back", "side", "top"):
                    photo_label = QLabel(f"Waiting for {role} camera")
                    photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    photo_label.setMinimumSize(180, 140)
                    photo_label.setStyleSheet("color: white; border: 1px solid #64748b;")
                    photo_row.addWidget(photo_label)
                    self.capture_photo_labels.append((role, photo_label))
                capture_layout.addLayout(photo_row)
                view.setStyleSheet("background-color: #2c3e50; padding: 20px;")
            else:
                view = QLabel(
                    f"<h1>{stage}</h1><p>Algorithmic logs and execution paths for node context tracking.</p>"
                )
                view.setAlignment(Qt.AlignmentFlag.AlignCenter)
                view.setStyleSheet("color: white; padding: 20px;")
            self.tab_stack.addWidget(view)
        pipeline_layout.addWidget(self.tab_stack)
        self.display_label = QLabel("Select an automated order node on the left to review metrics.")
        self.display_label.setStyleSheet("font-size: 13px; color: #7f8c8d;")
        pipeline_layout.addWidget(self.display_label)
        if self.order_queue_position in {"left", "top"}:
            layout.addWidget(self.order_queue)
            layout.addWidget(pipeline_container, 1)
        else:
            layout.addWidget(pipeline_container, 1)
            layout.addWidget(self.order_queue)
        self.order_queue.order_selected.connect(self.handle_order_selection)

    def handle_order_selection(self, order_id):
        self.update_display_details(order_id, self.order_queue.active_main_directory)
        self.order_queue.sync_order_widget_state(order_id)

    def handle_stage_navigation(self, index):
        self.tab_stack.setCurrentIndex(index)

    def update_display_details(self, order_id, active_directory):
        self.current_order_id = order_id
        self.current_order_directory = active_directory
        order_stage = "snapshot_pending"
        manifest_path = os.path.join(active_directory, order_id, "order_manifest.json")
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r") as file:
                    order_stage = json.load(file).get("stage", order_stage)
            except (OSError, json.JSONDecodeError):
                pass
        active_step = STAGE_INDEX_MAP.get(order_stage, 0)
        self.sim_timer.stop()
        self.pipeline_stepper.update_step_visuals(active_step)
        self.tab_stack.setCurrentIndex(active_step)
        self.display_label.setText(f"<h2>In view: {order_id.replace('_', ' ').title()}</h2><hr>")
        self.refresh_capture_photos(order_id, active_directory)

    def refresh_capture_photos(self, order_id, active_directory):
        order_path = os.path.join(active_directory, order_id)
        for role, label in self.capture_photo_labels:
            photo_path = os.path.join(order_path, f"{role}.jpg")
            if os.path.exists(photo_path):
                pixmap = QPixmap(photo_path)
                label.setPixmap(pixmap.scaled(
                    label.size(), Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))
                label.setText("")

    def start_mock_pipeline_animation(self):
        self.mock_progress_index = 0
        self.tab_stack.setCurrentIndex(0)
        self.pipeline_stepper.update_step_visuals(0)
        self.sim_timer.start(1200)

    def _advance_mock_pipeline(self):
        self.mock_progress_index += 1
        max_stages = len(self.pipeline_stepper.stages)
        if self.mock_progress_index >= max_stages:
            self.sim_timer.stop()
            self.pipeline_stepper.update_step_visuals(max_stages)
            return
        self.tab_stack.setCurrentIndex(self.mock_progress_index)
        self.pipeline_stepper.update_step_visuals(self.mock_progress_index)
        if not self.current_order_id or not self.current_order_directory:
            return
        stage_name = {v: k for k, v in STAGE_INDEX_MAP.items()}.get(
            self.mock_progress_index, "snapshot_pending"
        )
        manifest_path = os.path.join(
            self.current_order_directory, self.current_order_id, "order_manifest.json"
        )
        try:
            if os.path.exists(manifest_path):
                with open(manifest_path, "r") as file:
                    manifest = json.load(file)
                manifest["stage"] = stage_name
                with open(manifest_path, "w") as file:
                    json.dump(manifest, file, indent=4)
                self.order_state_updated.emit(self.current_order_id, manifest)
        except (OSError, json.JSONDecodeError):
            pass