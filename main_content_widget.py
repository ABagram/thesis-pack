import os
import json
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QLabel, QFrame, QStackedWidget
from PyQt6.QtGui import QFont
from pipeline_stepper import PipelineStepperWidget
import subprocess
import re
from copy_string_widget import CopyStringWidget
from wifi_status_widget import WifiStatusWidget

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

# Device/icon glyphs (private use area glyphs from the Poppins TTF)
GLYPH_CAMERA = "\ue438"
GLYPH_PC = "\ue30c"
GLYPH_CNC = "\ue131"
# Status glyphs: connected / disconnected
GLYPH_STATUS_CONNECTED = "\ue63e" 
GLYPH_STATUS_DISCONNECTED = "\ue648"
GLYPH_COPY = "\ue14d" # content_copy (Verify this hex matches your exact TTF font)

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
        self.current_ssid = None
        self.net_timer = QTimer(self)
        self.net_timer.setInterval(3000)  # poll every 3s
        self.net_timer.timeout.connect(self.refresh_network_status)
        self.init_ui()
        self.net_timer.start()

    def init_ui(self):
        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(15, 15, 15, 15)
        self.content_layout.setSpacing(15)
        
        self.network_details_frame = QFrame()
        self.content_layout.addWidget(self.network_details_frame)
        
        # Create a primary horizontal container to hold both functional halves
        network_main_layout = QHBoxLayout(self.network_details_frame)
        network_main_layout.setContentsMargins(12, 10, 12, 10)
        network_main_layout.setSpacing(20)

        # --- LEFT ZONE: Credentials (SSID/PW stacked vertically) ---
        credentials_widget = QWidget()
        credentials_layout = QGridLayout(credentials_widget)
        credentials_layout.setContentsMargins(0, 0, 0, 0)
        credentials_layout.setHorizontalSpacing(8)
        credentials_layout.setVerticalSpacing(6)

        # Populate SSID Row
        self.ssid_icon = QLabel("\ue63e")  # wifi icon
        self.ssid_icon.setStyleSheet("font-size: 14px; color: #64748b;")
        self.ssid_label = QLabel("SSID:")
        self.ssid_label.setStyleSheet("font-weight: bold; color: #475569; font-size: 12px")
        
        wifi_ssid = self.get_connected_ssid()
        self.ssid_detail = CopyStringWidget(wifi_ssid)

        credentials_layout.addWidget(self.ssid_icon, 0, 0)
        credentials_layout.addWidget(self.ssid_label, 0, 1)
        credentials_layout.addWidget(self.ssid_detail, 0, 2)

        # Populate Password Row
        self.pw_icon = QLabel("\ue73c")    # lock icon
        self.pw_icon.setStyleSheet("font-size: 14px; color: #64748b;")
        self.pw_label = QLabel("Pass:")
        self.pw_label.setStyleSheet("font-weight: bold; color: #475569; font-size: 12px;")

        wifi_pw = self.get_wifi_password(wifi_ssid) if wifi_ssid != "No Wi-Fi" else "Unavailable"
        self.pw_detail = CopyStringWidget(wifi_pw)
        self.pw_detail.setObjectName("PasswordDetail")

        credentials_layout.addWidget(self.pw_icon, 1, 0)
        credentials_layout.addWidget(self.pw_label, 1, 1)
        credentials_layout.addWidget(self.pw_detail, 1, 2)

        # Drop credentials stack into the main ribbon layout
        network_main_layout.addWidget(credentials_widget)

        # Add a spacer to separate credentials on the left from the statuses on the right
        network_main_layout.addStretch(1)
        
        # --- RIGHT ZONE: ESP Hardware Monitoring Strip ---
        status_strip_widget = QWidget()
        status_strip_layout = QHBoxLayout(status_strip_widget)
        status_strip_layout.setContentsMargins(0, 0, 0, 0)
        status_strip_layout.setSpacing(12)

        status_glyph = GLYPH_STATUS_CONNECTED if wifi_ssid != "No Wi-Fi" else GLYPH_STATUS_DISCONNECTED

        # -- 1. Camera Node Badge --
        self.camera_widget = WifiStatusWidget(
        system_name="ORDER CAPTURE STATION",
        glyph=GLYPH_CAMERA,
        temp_ssid="CAM_SETUP_AP", # set up via WiFiManager.autoConnect
        temp_pw="SST@2002", # set up via WiFiManager.autoConnect
        target_ssid=wifi_ssid,
        target_pw=wifi_pw,
        device_host="CAM-MASTER",
        disabled_tooltip=(
            "Camera captive portal "
            "setup broadcast cannot "
            "be found near laptop."
        )
    )
        status_strip_layout.addWidget(self.camera_widget)

        # -- 2. PC Server Node Badge --
        self.pc_widget = WifiStatusWidget(
        system_name="PC",
        glyph=GLYPH_PC,
        temp_ssid=None,
        temp_pw=None,
        target_ssid=wifi_ssid,
        target_pw=wifi_pw
    )
        status_strip_layout.addWidget(self.pc_widget)

        # -- 3. CNC Machine Node Badge --
        self.cnc_widget = WifiStatusWidget(
        system_name="BOX BLANK MAKER",
        glyph=GLYPH_CNC,
        temp_ssid="CUTTER_SETUP_AP", # set up via WiFiManager.autoConnect
        temp_pw="SST@2002", # set up via WiFiManager.autoConnect
        target_ssid=wifi_ssid,
        target_pw=wifi_pw,
        device_host="CUTTER-MASTER",  # change to real IP
    )
        status_strip_layout.addWidget(self.cnc_widget)

        # Mount the finished hardware monitoring strip into the ribbon
        network_main_layout.addWidget(status_strip_widget)

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

    def get_connected_ssid(self):
        """Get currently connected Wi-Fi SSID on Windows."""
        try:
            result = subprocess.check_output(
                ["netsh", "wlan", "show", "interfaces"],
                text=True,
                encoding="utf-8",
                errors="ignore"
            )

            match = re.search(
                r"^\s*SSID\s*:\s(.+)$",
                result,
                re.MULTILINE
            )

            if match:
                ssid = match.group(1).strip()

                # Ignore blank or disconnected states
                if ssid and ssid.lower() != "ssid":
                    return ssid

        except Exception as e:
            print("SSID Error:", e)

        return "No Wi-Fi"

    def is_5ghz_network(
        self,
        ssid
    ):
        if not ssid:
            return False

        ssid = ssid.upper()

        return (
            "_5G" in ssid
            or ssid.endswith("5G")
            or "5GHZ" in ssid
        )
    
    def refresh_network_status(self):
        """Polls the system for Wi-Fi changes and updates the UI if anything changed."""
        # --- 1. Keep your existing connection check logic ---
        ssid = self.get_connected_ssid()
        if ssid != self.current_ssid:
            self.current_ssid = ssid
            self.ssid_detail.update_text(
                ssid
            )

            pw = (
                self.get_wifi_password(
                    ssid
                )
                if ssid != "No Wi-Fi"
                else "Unavailable"
            )

            self.pw_detail.update_text(
                pw
            )

            # --------------------------------
            # Detect 5GHz network
            # --------------------------------
            if self.is_5ghz_network(
                ssid
            ):

                print(
                    "WARNING: ESP32 only "
                    "supports 2.4GHz Wi-Fi"
                )

                self.camera_widget.set_connected_network(
                    "⚠ 2.4GHz Required"
                )

                self.cnc_widget.set_connected_network(
                    "⚠ 2.4GHz Required"
                )

            else:

                self.camera_widget.target_ssid = (
                    ssid
                )

                self.camera_widget.target_pw = (
                    pw
                )

                self.cnc_widget.target_ssid = (
                    ssid
                )

                self.cnc_widget.target_pw = (
                    pw
                )

            self.pc_widget.target_ssid = (
                ssid
            )

            self.pc_widget.target_pw = (
                pw
            )
            
            self.camera_widget.target_ssid = ssid
            self.camera_widget.target_pw = pw

            self.pc_widget.target_ssid = ssid
            self.pc_widget.target_pw = pw

            self.cnc_widget.target_ssid = ssid
            self.cnc_widget.target_pw = pw

        status_text = "Online" if ssid != "No Wi-Fi" else "Offline"
        if hasattr(self, 'wifi_status'):
            self.wifi_status.setText(f"Status: {status_text}")

        # --- 3. Scan nearby SSIDs to dynamically enable/disable the "Setup" buttons ---
        visible_ssids = self.get_visible_ssids()
        
        if hasattr(self, 'camera_widget'):
            self.camera_widget.poll_device_network()
        if hasattr(self, 'pc_widget'):
            self.pc_widget.set_online_status(
                ssid != "No Wi-Fi"
            )

            self.pc_widget.set_connected_network(
                ssid
            )
            self.pc_widget.poll_device_network()
            
        if hasattr(self, 'cnc_widget'):
            self.cnc_widget.poll_device_network()
            
        pc_online = (
            ssid != "No Wi-Fi"
        )

        self.pc_widget.set_online_status(
            pc_online
        )

        self.pc_widget.set_connected_network(
            ssid
        )

    def get_wifi_password(self, ssid):
        """Get saved password for a Wi-Fi profile."""
        try:
            result = subprocess.check_output(
                ["netsh", "wlan", "show", "profile", ssid, "key=clear"],
                text=True,
                encoding="utf-8",
                errors="ignore"
            )

            match = re.search(
                r"Key Content\s*:\s(.+)",
                result
            )

            if match:
                return match.group(1).strip()

        except Exception as e:
            print("Password Error:", e)

        return "Unavailable"
    
    def get_visible_ssids(self):
        """Scan and return a list of all unique Wi-Fi SSIDs currently in range."""
        try:
            # This command lists all broadcasted Wi-Fi networks in range
            result = subprocess.check_output(
                ["netsh", "wlan", "show", "networks"],
                text=True,
                encoding="utf-8",
                errors="ignore"
            )
            
            # Regex to capture the SSID name line
            # Match lines like "SSID 1 : My_Camera_Network"
            ssids = re.findall(r"SSID\s+\d+\s+:\s+(.+)", result)
            
            # Return a list of clean, trimmed strings
            return [ssid.strip() for ssid in ssids if ssid.strip()]
            
        except Exception as e:
            print("SSID Scan Error:", e)
            return []
    
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