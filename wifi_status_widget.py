from PyQt6.QtWidgets import QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QToolTip
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread, QRect
from PyQt6.QtGui import QFont, QIcon, QPixmap
from PyQt6 import sip
import qtawesome, qtmdi
import requests
from load_icon import load_icon
from read_pc_ssid import read_pc_ssid
from wifi_setup_overlay import WifiSetupOverlay
import subprocess

ICON_WARNING = "icons/warning.svg"
ICON_OFFLINE = "icons/globe_2_cancel.svg"
ICON_ONLINE = "icons/wifi.svg"

class WifiStatusWidget(QWidget):
    # Signals to communicate back to your main window if needed
    connection_started = pyqtSignal(str)  # Emits system name
    connection_finished = pyqtSignal(str, bool)  # Emits system name and success status

    def __init__(
        self,
        system_name: str,
        glyph: str,
        temp_ssid: str,
        temp_pw: str | None,
        target_ssid: str,
        target_pw: str,
        disabled_tooltip: str = (
            "Target setup network not detected."
        ),
        device_host=None,
        parent=None
    ):
        super().__init__(parent)
        
        self.showing_mismatch_tooltip = False
        
        self.system_name = system_name
        self.glyph = glyph
        self.temp_ssid = temp_ssid
        self.temp_pw = temp_pw
        self.target_ssid = target_ssid
        self.target_pw = target_pw
        self.disabled_tooltip = disabled_tooltip
        self.device_host = (device_host)
        
        self.connected_network = None

        self.init_ui()
        
    def init_ui(self):
        
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.badge = QFrame(self)
        self.badge.setObjectName("WifiStatusWidget")
        root_layout.addWidget(self.badge)

        badge_layout = QVBoxLayout(self.badge)
        badge_layout.setContentsMargins(8, 6, 8, 6)
        badge_layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.icon_label = QLabel(self.glyph)
        self.icon_label.setObjectName("SystemIcon")

        self.text_label = QLabel(
            self.system_name.title(),
            self.badge
        )
        self.text_label.setObjectName("SystemName")
        
        top_row.addWidget(self.icon_label)
        top_row.addWidget(self.text_label)

        bottom_row = QHBoxLayout()
        bottom_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.connect_status = QLabel()
        self.connect_status.setFixedSize(20, 20)
        self.connect_status.setPixmap(load_icon(ICON_OFFLINE, color="#DC2626"))
        self.connect_status.setObjectName("Connect_Status_Offline")

        self.ssid_label = QLabel("SSID:")
        self.ssid_label.setStyleSheet("""
            text-align: left;
            padding: 0;
            border: none;
        """)
        self.network_label = QLabel("Disconnected")
        self.network_label.setObjectName("WifiStatusWidget_SSID_Name")
        
        bottom_row.addWidget(self.connect_status)
        bottom_row.addWidget(self.ssid_label)
        bottom_row.addWidget(self.network_label)

        # Add rows to badge
        badge_layout.addLayout(top_row)
        badge_layout.addLayout(bottom_row)

    def poll_device_network(self):
        if not self.device_host:
            return

        if self.temp_ssid and not hasattr(self, "_setup_running"):

            result = subprocess.run(
                ["netsh", "wlan", "show", "networks"],
                capture_output=True,
                text=True
            )

            if self.temp_ssid in result.stdout:
                print("Setup AP detected immediately.")
                self._setup_running = True
                self.start_setup_overlay()
                return
            
        try:
            response = requests.get(f"http://{self.device_host}.local/status", timeout=2)
            data = response.json()
            
            esp_connected = data.get("connected", False)
            esp_ssid = data.get("ssid", None)
            
            self.esp_ssid = esp_ssid
            self.set_connected_network(esp_ssid)

            pc_ssid = read_pc_ssid()
            is_valid_online = esp_connected and (pc_ssid == esp_ssid)
            self.set_online_status(is_valid_online)

            # --- PERSISTENT TOOLTIP LOGIC ---
            if pc_ssid is not None and esp_ssid is not None and pc_ssid != esp_ssid:
                print(f"SSID mismatch: PC='{pc_ssid}' {self.device_host}='{esp_ssid}'")
                self.connect_status.setPixmap(load_icon(ICON_WARNING, color="#f45900"))
                self.network_label.setText(f"{esp_ssid} (Mismatch)")

                # If we haven't shown it yet, spawn the persistent tooltip
                if not self.showing_mismatch_tooltip:
                    # Map the tooltip location right underneath the network label
                    global_pos = self.network_label.mapToGlobal(self.network_label.rect().bottomLeft())
                    global_pos.setY(global_pos.y() + 5)
                    
                    warning_msg = (
                        f"⚠️ <b>SSID Mismatch Detected!</b><br>"
                        f"Your PC is on: <b>{pc_ssid}</b><br>"
                        f"Device is on: <b>{esp_ssid}</b><br><br>"
                        f"Please switch your PC network to match."
                    )
                    
                    # Passing 0 as the third argument tells Qt to keep it open indefinitely
                    QToolTip.showText(global_pos, warning_msg, self.network_label, QRect(), 5)
                    self.showing_mismatch_tooltip = True
            else:
                # If they match now, or went totally offline, clear the persistent tooltip instantly
                if self.showing_mismatch_tooltip:
                    QToolTip.hideText()
                    self.showing_mismatch_tooltip = False

        except Exception as e:
            # print(f"{self.system_name} status error:", e)
            self.set_online_status(False)
            self.set_connected_network("Offline")
            # Clear it if connection drops completely
            if self.showing_mismatch_tooltip:
                QToolTip.hideText()
                self.showing_mismatch_tooltip = False
                
    def set_connected_network(self, ssid):
        self.connected_network = ssid

        if hasattr(self, "network_label"):
            self.network_label.setText(
                ssid or "Disconnected"
            )
        
    def set_online_status(self, is_online: bool):
        """Updates the status badge color and glyph"""

        # Prevent crashes if QLabel was deleted
        if not hasattr(self, "connect_status"):
            return

        if sip.isdeleted(self.connect_status):
            return

        if is_online:
            self.connect_status.setPixmap(load_icon(ICON_ONLINE, color="#16A34A"))
            self.connect_status.setObjectName("Connect_Status_Online")
        else:
            self.connect_status.setPixmap(load_icon(ICON_OFFLINE, color="#DC2626"))
            self.connect_status.setObjectName("Connect_Status_Offline")
            
    def start_setup_overlay(self):
        print("Opening WifiSetupOverlay")
        # Find top level main window to apply overlay to
        self.overlay = WifiSetupOverlay(
            system_name=self.system_name,
            temp_ssid=self.temp_ssid,
            temp_pw = self.temp_pw,
            target_ssid=self.target_ssid,
            target_pw=self.target_pw
        )
        # Connect to overlay finish event to flip icon colors
        self.overlay.setup_completed.connect(self.handle_setup_success)
        self.overlay.show()

    def handle_setup_success(self, success: bool):
        
        self._setup_running = False
        
        self.set_online_status(success)
        # If setup succeeded once, switch the button into force-reset mode
        if success:
            try:
                self.enable_force_reset(True)
            except Exception:
                pass

        self.connection_finished.emit(self.system_name, success)
