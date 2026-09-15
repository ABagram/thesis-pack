import os
import json
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QLabel, QFrame, QStackedWidget
from PyQt6.QtGui import QHideEvent, QShowEvent
from pipeline_stepper import PipelineStepperWidget
import subprocess
import re
from components.copy_string_widget import CopyStringWidget
from wifi_status_widget import WifiStatusWidget
from load_icon import load_icon
from wifi_network_monitor import WifiNetworkMonitor
from wifi_credential_manager import WifiCredentialManager
from wifi_udp_listener import WifiUdpListener
from components.anchored_tooltip import AnchoredTooltip
from components.inline_badge import InlineBadgeParagraphWrapper
from esp_wifi_guidance import show_esp_wifi_guidance
from branding import *
from components.org_chart_container import OrgChartContainer
from new_order import *

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
        self.wifi_warning_toast = None
        self.current_wifi_is_5ghz = False
        self.current_wifi_band = "Unknown"
        self.wifi_band_tooltip = None
        self.sim_timer = QTimer(self)
        self.sim_timer.timeout.connect(self._advance_mock_pipeline)
        self.current_ssid = None

        self.init_ui()

        # ============================================================
        # Wi-Fi network monitor
        # ============================================================

        self.network_monitor = WifiNetworkMonitor(
            setup_ssids=[
                "OSS_MASTER_SETUP_AP",
                "CCP_MASTER_SETUP_AP"
            ]
        )

        self.network_monitor.network_changed.connect(
            self.handle_network_changed
        )

        self.network_monitor.setup_ap_detected.connect(
            self.handle_setup_ap_detected
        )

        self.udp_listener = WifiUdpListener()
        self.udp_listener.status_received.connect(
            self.handle_udp_status
        )

        self.network_monitor.start_scanning()

        # ============================================================
        # ESP online/offline state → WLAN scanner control
        # ============================================================

        self.oss_master_status_widget.device_online_changed.connect(
            lambda online: self.handle_device_online_changed(
                "oss-master",
                online
            )
        )

        self.oss_master_status_widget.device_online_changed.connect(
            lambda online: self.sync_esp_wifi_guidance() # ensures that tooltip showing network that the ESP is connected to only shows if there's a network mismatch and is receiving UDP packets
        )

        self.cnc_widget.device_online_changed.connect(
            lambda online: self.handle_device_online_changed(
                "cnc",
                online
            )
        )

        self.cnc_widget.device_online_changed.connect(
            lambda online: self.sync_esp_wifi_guidance()
            # ensures that tooltip showing network that the ESP is connected to only shows if there's a network mismatch and is receiving UDP packets
        )

        self.network_monitor.start()

    def init_ui(self):
        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(15, 15, 15, 15)
        self.content_layout.setSpacing(15)

        self.view_stack = QStackedWidget()
        self.network_page = QWidget()
        self.pipeline_page = QWidget()
        self.network_page_layout = QVBoxLayout(self.network_page)
        self.pipeline_page_layout = QVBoxLayout(self.pipeline_page)
        self.view_stack.addWidget(self.network_page)
        self.view_stack.addWidget(self.pipeline_page)
        self.content_layout.addWidget(self.view_stack)
        
        self.network_details_frame = QFrame()
        self.network_page_layout.addWidget(self.network_details_frame)
        
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
        self.ssid_icon = QLabel()  # wifi icon
        self.ssid_icon.setPixmap(load_icon(ICON_WIFI, size=14, color="#64748b"))
        self.ssid_icon.setStyleSheet("font-size: 14px; color: #64748b;")
        self.ssid_label = QLabel("SSID:")
        self.ssid_label.setStyleSheet("font-weight: bold; color: #475569; font-size: 12px")
        
        wifi_ssid = self.get_connected_ssid()
        self.ssid_detail = CopyStringWidget(wifi_ssid)
        self.wifi_band_badge = QLabel("Unknown")
        self.wifi_band_badge.setObjectName("WifiBandBadge")
        self.wifi_band_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.wifi_band_badge.setFixedHeight(24)

        credentials_layout.addWidget(self.ssid_icon, 0, 0)
        credentials_layout.addWidget(self.ssid_label, 0, 1)
        credentials_layout.addWidget(self.ssid_detail, 0, 2)
        credentials_layout.addWidget(self.wifi_band_badge, 0, 3)

        # Populate Password Row
        self.pw_icon = QLabel() 
        self.pw_icon.setPixmap(load_icon(ICON_LOCK, size=14, color="#64748b"))
        self.pw_icon.setStyleSheet("font-size: 14px; color: #64748b;")
        self.pw_label = QLabel("Pass:")
        self.pw_label.setStyleSheet("font-weight: bold; color: #475569; font-size: 12px;")

        wifi_pw = self.get_wifi_password(wifi_ssid) if wifi_ssid != "No Wi-Fi" else "Unavailable"
        self.pw_detail = CopyStringWidget(wifi_pw)
        self.pw_detail.setObjectName("PasswordDetail")

        credentials_layout.addWidget(self.pw_icon, 1, 0)
        credentials_layout.addWidget(self.pw_label, 1, 1)
        credentials_layout.addWidget(self.pw_detail, 1, 2)

        network_main_layout.addWidget(credentials_widget)

        network_main_layout.addStretch(1)
        
        wifi_status_widget_hierarchy_chart = OrgChartContainer()

        self.pc_widget = WifiStatusWidget(
                system_name="This PC",
                icon_path=ICON_PC,
                ap_ssid=None,
                temp_pw=None,
                target_ssid=wifi_ssid,
                target_pw=wifi_pw,
                is_esp=False
            )
        
        self.oss_master_status_widget = WifiStatusWidget(
        system_name="Order Scanning Station",
        icon_path=ICON_CAMERA,
        temp_pw="SST@2002", # set up via WiFiManager.autoConnect
        target_ssid=wifi_ssid,
        target_pw=wifi_pw,
        device_host="OSS-MASTER",
        ap_ssid="OSS_MASTER_SETUP_AP",
        mac_address="68:09:47:37:81:24",
        udp_device_id="oss-master",
        disabled_tooltip=(
            "Camera captive portal "
            "setup broadcast cannot "
            "be found near laptop."
        )
    )

        #self.oss_slave_x_status_widget = WifiStatusWidget(
        #    system_name="Front Camera",
        #    icon_path=ICON_CAMERA,
        #    mac_address="c0:4e:30:2f:28:94",
        #)
        
        self.cnc_widget = WifiStatusWidget(
        system_name="Cutting and Creasing Plotter",
        icon_path=ICON_BOX,
        temp_pw="SST@2002", # set up via WiFiManager.autoConnect
        target_ssid=wifi_ssid,
        target_pw=wifi_pw,
        device_host="CCP-MASTER",
        ap_ssid="CCP_MASTER_SETUP_AP",
        udp_device_id="cnc",
    )
        wifi_status_widget_hierarchy_chart.add_tier([self.pc_widget])
        wifi_status_widget_hierarchy_chart.add_tier([
            self.oss_master_status_widget,
            self.cnc_widget
        ])

        self.update_wifi_band()

        self.wifi_band_timer = QTimer(self)
        self.wifi_band_timer.timeout.connect(self.update_wifi_band)
        self.wifi_band_timer.start(3000)

        # Mount the finished hardware monitoring strip into the ribbon
        network_main_layout.addWidget(wifi_status_widget_hierarchy_chart)

        self.pipeline_page_layout.setContentsMargins(0, 0, 0, 0)

        # 2. Dynamic Component Stepper Instantiation
        self.pipeline_stepper = PipelineStepperWidget(PRODUCTION_STAGES, GLYPH_MAP)
        self.pipeline_stepper.stage_selected.connect(self.handle_stage_navigation)
        self.pipeline_page_layout.addWidget(self.pipeline_stepper)

        # 3. Stacked Containers for Viewports
        self.tab_stack = QStackedWidget()
        self.tab_stack.setStyleSheet("background-color: #2c3e50; border-radius: 6px; border: 1px solid #34495e;")
        
        # Generate view panels dynamically to match your step array lengths
        for stage in PRODUCTION_STAGES:
            view = QLabel(f"<h1>{stage}</h1><p>Algorithmic logs and execution paths for node context tracking.</p>")
            view.setAlignment(Qt.AlignmentFlag.AlignCenter)
            view.setStyleSheet("color: white; padding: 20px;")
            self.tab_stack.addWidget(view)
            
        self.pipeline_page_layout.addWidget(self.tab_stack)

        self.display_label = QLabel("Select an automated order node on the left to review metrics.")
        self.display_label.setStyleSheet("font-size: 13px; color: #7f8c8d;")
        self.pipeline_page_layout.addWidget(self.display_label)

    def show_view(self, view_id):
        if view_id == "network":
            self.view_stack.setCurrentWidget(self.network_page)
        elif view_id == "pipeline":
            self.view_stack.setCurrentWidget(self.pipeline_page)

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

    def get_connected_wifi_channel(self):
        """Return the connected WLAN channel reported by Windows."""
        try:
            result = subprocess.check_output(
                ["netsh", "wlan", "show", "interfaces"],
                text=True,
                encoding="utf-8",
                errors="ignore"
            )

            match = re.search(
                r"^\s*Channel\s*:\s*(\d+)",
                result,
                re.MULTILINE
            )
            return int(match.group(1)) if match else None

        except (OSError, ValueError):
            return None

    def get_connected_wifi_band(self):
        channel = self.get_connected_wifi_channel()
        if channel is None:
            return "Unknown"
        if 1 <= channel <= 14:
            return "2.4 GHz"
        if channel >= 36:
            return "5 GHz"
        return "Other"

    def is_5ghz_network(self, ssid=None):
        """Determine the connected band from its WLAN channel, not its SSID."""
        return self.get_connected_wifi_band() == "5 GHz"

    def get_available_24ghz_ssids(self):
        """Return nearby SSIDs advertising at least one 2.4 GHz channel."""
        try:
            result = subprocess.check_output(
                ["netsh", "wlan", "show", "networks", "mode=bssid"],
                text=True,
                encoding="utf-8",
                errors="ignore"
            )
        except OSError:
            return []

        networks = []
        blocks = re.split(
            r"(?=^\s*SSID\s+\d+\s*:)",
            result,
            flags=re.MULTILINE
        )

        for block in blocks:
            ssid_match = re.search(
                r"^\s*SSID\s+\d+\s*:\s*(.*)$",
                block,
                re.MULTILINE
            )
            if not ssid_match:
                continue

            network_ssid = ssid_match.group(1).strip()
            if not network_ssid or network_ssid == "<Hidden Network>":
                continue

            channels = re.findall(
                r"^\s*Channel\s*:\s*(\d+)",
                block,
                re.MULTILINE
            )
            if any(1 <= int(channel) <= 14 for channel in channels):
                networks.append(network_ssid)

        return list(dict.fromkeys(networks))

    def show_wifi_band_tooltip(self, band):
        if self.wifi_band_tooltip is not None:
            return

        print(f"Creating Wi-Fi tooltip for band: {band}")

        if band == "5 GHz":
            text = (
                "Switch the PC to a 2.4 GHz Wi-Fi network."
            )
        else:
            text = (
                "The PC Wi-Fi band is not supported by the ESP devices. "
                "Switch to a 2.4 GHz Wi-Fi network."
            )

        # ---------------------------------------------------------
        # Tooltip content
        # ---------------------------------------------------------

        content = InlineBadgeParagraphWrapper(
            text_font_color="#ffffff",
            badge_font_color="#991b1b",
            badge_bg_color="#fee2e2",
            badge_border_color="#fecaca",
            badge_icon_color="#991b1b",
        )

        content.insert_text("Switch the ")
        content.insert_badge_with_icon(
            "PC",
            ICON_PC,
        )
        content.insert_text(" to a ")
        content.insert_badge_with_icon(
            "2.4 GHz",
            ICON_WIFI_CHANNEL,
        )
        content.insert_text(" Wi-Fi network.")

        self.wifi_band_tooltip = AnchoredTooltip(
            content=content,
            target=self.pc_widget,
            position="down",
            tooltip_color="#991b1b",
        )

        self.wifi_band_tooltip.show()
        
    def clear_wifi_band_tooltip(self):
        tooltip = self.wifi_band_tooltip
        self.wifi_band_tooltip = None

        print("Clearing Wi-Fi tooltip")
        
        if tooltip is not None:
            tooltip.close()
            tooltip.deleteLater()
            
    def update_wifi_band(self):
        band = self.get_connected_wifi_band()
        is_5ghz = band == "5 GHz"
        self.current_wifi_band = band
        self.current_wifi_is_5ghz = is_5ghz

        badge_colors = {
            "2.4 GHz": ("#166534", "#dcfce7", "#bbf7d0"),
            "5 GHz": ("#b91c1c", "#fee2e2", "#fecaca"),
            "Other": ("#b91c1c", "#fee2e2", "#fecaca"),
            "Unknown": ("#64748b", "#f1f5f9", "#cbd5e1"),
        }
        text_color, background, border = badge_colors[band]
        self.wifi_band_badge.setText(band)
        self.wifi_band_badge.setStyleSheet(
            f"color: {text_color}; background: {background}; "
            f"border: 1px solid {border}; border-radius: 6px; "
            "padding: 2px 8px; font-size: 10px; font-weight: 600;"
        )

        # Only the PC badge describes the laptop's Wi-Fi band. ESP badges
        # describe their own heartbeat reachability instead.
        self.pc_widget.set_laptop_band(is_5ghz)

        if band == "2.4 GHz":
            self.clear_wifi_band_tooltip()
        elif band in ("5 GHz", "Other"):
            self.show_wifi_band_tooltip(band)

    def handle_network_changed(self, ssid):
        """Handle an actual Windows Wi-Fi/network change."""
        print(f"Wi-Fi network changed: {ssid}")

        self.refresh_network_status(ssid)
        
    def refresh_network_status(self, ssid=None):
        """Update the UI using the current Wi-Fi SSID."""
        if ssid is None:
            ssid = self.get_connected_ssid()
        self.update_wifi_band()
        network_changed = ssid != self.current_ssid

        if network_changed:
            self.current_ssid = ssid
            self.ssid_detail.update_text(ssid)

            pw = (
                self.get_wifi_password(
                    ssid
                )
                if ssid != "No Wi-Fi"
                else "Unavailable"
            )

            self.pw_detail.update_text(pw)

            self.pc_widget.target_ssid = (
                ssid
            )

            self.pc_widget.target_pw = (
                pw
            )
            
            self.oss_master_status_widget.target_ssid = ssid
            self.oss_master_status_widget.target_pw = pw

            self.pc_widget.target_ssid = ssid
            self.pc_widget.target_pw = pw

            self.cnc_widget.target_ssid = ssid
            self.cnc_widget.target_pw = pw

        if network_changed:

            self.oss_master_status_widget.heartbeat_received = False
            self.oss_master_status_widget.heartbeat_matches_pc = False

            self.cnc_widget.heartbeat_received = False
            self.cnc_widget.heartbeat_matches_pc = False

            self.clear_esp_wifi_guidance(
                self.oss_master_status_widget
            )
            self.clear_esp_wifi_guidance(
                self.cnc_widget
            )
            
        self.sync_esp_wifi_guidance()

        # --- 3. Scan nearby SSIDs to dynamically enable/disable the "Setup" buttons ---
        if hasattr(self, 'pc_widget'):
            self.pc_widget.set_online_status(
                ssid != "No Wi-Fi"
            )

            self.pc_widget.set_connected_network(
                ssid
            )
        pc_online = (
            ssid != "No Wi-Fi"
        )

        self.pc_widget.set_online_status(
            pc_online
        )

        self.pc_widget.set_connected_network(
            ssid
        )

    def handle_udp_status(self, device_id, is_connected, esp_ssid):
        pc_ssid = self.current_ssid
        if pc_ssid is None:
            pc_ssid = self.get_connected_ssid()

        if device_id == "oss-master":
            self.oss_master_status_widget.handle_udp_status(
                device_id, is_connected, esp_ssid, pc_ssid
            )
        elif device_id == "cnc":
            self.cnc_widget.handle_udp_status(
                device_id, is_connected, esp_ssid, pc_ssid
            )

        self.sync_esp_wifi_guidance()

    def sync_esp_wifi_guidance(self):
        pc_ssid = self.current_ssid
        if pc_ssid is None:
            pc_ssid = self.get_connected_ssid()

        for widget in (self.oss_master_status_widget, self.cnc_widget):
            esp_ssid = getattr(widget, "_heartbeat_ssid", None)
            esp_heartbeat = getattr(
                widget,
                "heartbeat_received",
                False
            )

            if esp_heartbeat and esp_ssid and esp_ssid != pc_ssid:
                show_esp_wifi_guidance(
                    self,
                    widget,
                    esp_ssid
                )
            else:
                self.clear_esp_wifi_guidance(widget)


    def clear_esp_wifi_guidance(self, widget):
        tooltip = getattr(self, "esp_wifi_tooltips", {}).pop(widget, None)
        if tooltip is not None:
            tooltip.close()
            tooltip.deleteLater()

    def get_wifi_password(self, ssid):
        """Get the password stored by Windows for a Wi-Fi profile."""

        password = WifiCredentialManager.get_password(ssid)

        if password is not None:
            return password

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

    def handle_device_online_changed(
        self,
        system_name,
        is_online
    ):
        print(
            f"{system_name} device online state: "
            f"{is_online}"
        )

        oss_master_online = getattr(
            self.oss_master_status_widget,
            "_device_online",
            False
        )

        cnc_online = getattr(
            self.cnc_widget,
            "_device_online",
            False
        )

        # --------------------------------------------------------
        # If either ESP is offline, keep WLAN scanning enabled.
        # --------------------------------------------------------

        if not oss_master_online or not cnc_online:

            print(
                "At least one ESP is offline. "
                "WLAN setup-AP scanning enabled."
            )

            self.network_monitor.start_scanning()

        # --------------------------------------------------------
        # Only stop scanning when BOTH ESPs are online.
        # --------------------------------------------------------

        else:

            print(
                "Both ESPs are online. "
                "WLAN setup-AP scanning disabled."
            )

            self.network_monitor.stop_scanning()

    def handle_setup_ap_detected(self, ssid):

        print(
            f"Setup AP detected by Wi-Fi monitor: {ssid}"
        )

        if ssid == "OSS_MASTER_SETUP_AP" and getattr(
            self.oss_master_status_widget,
            "_setup_running",
            False
        ):
            return

        if ssid == "CUTTER_SETUP_AP" and getattr(
            self.cnc_widget,
            "_setup_running",
            False
        ):
            return

        # We found the AP, so stop requesting WLAN scans.
        self.network_monitor.stop_scanning()

        if ssid == "OSS_MASTER_SETUP_AP":

            self.oss_master_status_widget._setup_running = True

            self.oss_master_status_widget.start_setup_overlay()

        elif ssid == "CUTTER_SETUP_AP":

            self.cnc_widget._setup_running = True

            self.cnc_widget.start_setup_overlay()
            
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

    def closeEvent(self, a0):
        if hasattr(self, "network_monitor"):
            self.network_monitor.stop()

        super().closeEvent(a0)