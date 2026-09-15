from PyQt6.QtWidgets import QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QToolTip, QGridLayout, QSizePolicy
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRect
from PyQt6.QtGui import QFont, QIcon, QPixmap
from PyQt6 import sip
from load_icon import load_icon
from read_pc_ssid import read_pc_ssid
from wifi_setup_overlay import WifiSetupOverlay
from wifi_credential_manager import WifiCredentialManager
from components.icon_badge import IconBadge
from branding import *

STATUS_ICON_SIZE = 14

class WifiStatusWidget(QWidget):
    # Signals to communicate back to your main window if needed
    connection_started = pyqtSignal(str)  # Emits system name
    connection_finished = pyqtSignal(str, bool)  # Emits system name and success status
    device_online_changed = pyqtSignal(bool)

    def __init__(
        self,
        system_name: str,
        icon_path: str,
        temp_pw: str | None,
        target_ssid: str,
        target_pw: str,
        disabled_tooltip: str = (
            "Target setup network not detected."
        ),
        device_host=None,
        ap_ssid=None,
        mac_address=None,
        udp_device_id: str | None = None,
        is_esp: bool = True,
        parent=None
    ):
        super().__init__(parent)
        
        self.showing_mismatch_tooltip = False

        self.is_esp = is_esp
        self.system_name = system_name
        self.icon_path = icon_path
        self.temp_pw = temp_pw
        self.target_ssid = target_ssid
        self.target_pw = target_pw
        self.disabled_tooltip = disabled_tooltip
        
        # Store values with distinct names to prevent overwriting
        self._device_host_val = device_host
        self._ap_ssid_val = ap_ssid
        self._mac_address_val = mac_address
        
        self.udp_device_id = udp_device_id
        self.laptop_on_5ghz = False
        self.heartbeat_received = False
        self.heartbeat_matches_pc = False
        self._heartbeat_ssid = None
        
        self.connected_network = None

        self.setSizePolicy(
            QSizePolicy.Policy.Preferred, 
            QSizePolicy.Policy.Maximum
        )
                
        self.init_ui()

        if self.udp_device_id:
            self._setup_udp_watchdog()

    def init_ui(self):
        root_layout = QVBoxLayout(self)  # Fixed: changed from QGridLayout to QVBoxLayout
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.status_widget = QFrame(self)
        self.status_widget.setObjectName("WifiStatusWidget")
        root_layout.addWidget(self.status_widget)

        badge_layout = QVBoxLayout(self.status_widget)
        badge_layout.setContentsMargins(8, 6, 8, 6)
        badge_layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.system_name_label = QLabel()
        self.system_name_label.setText(f'<p style="line-height: 80%; width: 30px">{self.system_name}</p>')
        self.system_name_label.setWordWrap(True)
        self.system_name_label.setObjectName("SystemName")

        self.icon_badge = IconBadge(
            icon_path=self.icon_path,
            icon_size=16,
            icon_color=text_slate_400,
            badge_color=bg_slate_50
        )

        top_row.addWidget(self.system_name_label)
        top_row.addStretch()
        top_row.addWidget(self.icon_badge)

        bottom_row = QVBoxLayout()
        bottom_row.setAlignment(Qt.AlignmentFlag.AlignLeft)

        connect_status_row = QHBoxLayout()
        connect_status_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        bottom_row.addLayout(connect_status_row)

        self.connect_status_icon = IconBadge(
            icon_path=ICON_OFFLINE,
            icon_size=STATUS_ICON_SIZE,
            icon_color=text_red_600,
            badge_color=bg_red_50,
            shape="circle",
        )
        
        self.network_label = QLabel("Disconnected")
        self.network_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.network_label.setObjectName("WifiStatusWidget_SSID_Name")

        # Create title and value widgets properly
        device_host_title = QLabel("Device Host:")
        device_host_title.setStyleSheet(f"""
                font-size: 10px;
                color: {text_slate_600};
            """)
        self.device_host_label = QLabel(self._device_host_val or "N/A")
        self.device_host_label.setStyleSheet("font-size: 10px;")

        ap_ssid_title = QLabel("AP SSID:")
        ap_ssid_title.setStyleSheet(f"""
                font-size: 10px;
                color: {text_slate_600};
            """)
        self.ap_ssid_label = QLabel(self._ap_ssid_val or "N/A")
        self.ap_ssid_label.setStyleSheet("font-size: 10px;")

        mac_address_title = QLabel("MAC Address:")
        mac_address_title.setStyleSheet(f"""
                font-size: 10px;
                color: {text_slate_600};
            """)
        self.mac_address_label = QLabel(self._mac_address_val or "N/A")
        self.mac_address_label.setStyleSheet("font-size: 10px;")
        
        # Nest the QGridLayout inside the bottom vertical layout
        self.device_details_layout = QGridLayout()
        self.device_details_layout.addWidget(device_host_title, 0, 0)
        self.device_details_layout.addWidget(self.device_host_label, 0, 1)
        self.device_details_layout.addWidget(ap_ssid_title, 1, 0)
        self.device_details_layout.addWidget(self.ap_ssid_label, 1, 1)
        self.device_details_layout.addWidget(mac_address_title, 2, 0)
        self.device_details_layout.addWidget(self.mac_address_label, 2, 1)

        connect_status_row.addWidget(self.connect_status_icon)
        connect_status_row.addWidget(self.network_label)
        if self.is_esp:
            bottom_row.addLayout(self.device_details_layout)

        # Add rows to badge
        badge_layout.addLayout(top_row)
        badge_layout.addLayout(bottom_row)
        
    def set_connected_network(self, ssid):
        self.connected_network = ssid
        if not self.udp_device_id:
            self.heartbeat_received = bool(ssid)
            self.heartbeat_matches_pc = self.heartbeat_received
        self._heartbeat_ssid = ssid
        self._refresh_network_label()

    def set_laptop_band(self, is_5ghz):
        self.laptop_on_5ghz = is_5ghz
        self._refresh_network_label()

    def _refresh_network_label(self):
        if not hasattr(self, "network_label"):
            return

        # 1. Band Warning State (Laptop on 5 GHz)
        if self.laptop_on_5ghz:
            label_text = "2.4 GHz Wi-Fi Required"
            connect_status_icon_path = ICON_WIFI_CHANNEL
            icon_color = text_blue_600
            badge_color = bg_blue_50
        
        # 2. Connected & Matched State
        elif (
            self.heartbeat_received
            and self.heartbeat_matches_pc
            and self._heartbeat_ssid
        ):
            label_text = self._heartbeat_ssid
            connect_status_icon_path = ICON_WIFI
            icon_color = text_green_600
            badge_color = bg_green_50
            
        # 3. Network Mismatch State (Receiving UDP, but SSIDs differ)
        elif (
            self.heartbeat_received
            and not self.heartbeat_matches_pc
        ):
            label_text = "Network Mismatch"
            connect_status_icon_path = ICON_ROUTER_OFF 
            icon_color = text_orange_600
            badge_color = bg_orange_50

        # 4. Disconnected State
        else:
            label_text = "Disconnected"
            connect_status_icon_path = ICON_OFFLINE
            icon_color = text_red_600
            badge_color = bg_red_50

        self.network_label.setText(label_text)
        
        # Call the update method instead of re-running init_ui()
        self.connect_status_icon.update_badge(
            icon_path=connect_status_icon_path,
            icon_color=icon_color,
            badge_color=badge_color
        )

    def _handle_device_status(
        self,
        esp_connected,
        esp_ssid,
        pc_ssid=None
    ):

        self.esp_ssid = esp_ssid
        self.heartbeat_received = bool(esp_connected and esp_ssid)
        self._heartbeat_ssid = esp_ssid

        if pc_ssid is None:
            pc_ssid = read_pc_ssid()

        is_valid_online = (
            esp_connected
            and bool(esp_ssid)
            and pc_ssid == esp_ssid
        )

        self.heartbeat_matches_pc = is_valid_online
        self._refresh_network_label()

        self.set_online_status(
            is_valid_online
        )

        if (
            pc_ssid is not None
            and esp_ssid is not None
            and pc_ssid != esp_ssid
        ):

            print(
                f"SSID mismatch: "
                f"PC='{pc_ssid}' "
                f"{self._device_host_val}='{esp_ssid}'"
            )

            if not self.showing_mismatch_tooltip:

                global_pos = (
                    self.network_label.mapToGlobal(
                        self.network_label.rect().bottomLeft()
                    )
                )

                global_pos.setY(
                    global_pos.y() + 5
                )

                warning_msg = (
                    f"⚠️ <b>SSID Mismatch Detected!</b><br>"
                    f"Your PC is on: <b>{pc_ssid}</b><br>"
                    f"Device is on: <b>{esp_ssid}</b><br><br>"
                    f"Please switch your PC network to match."
                )

                QToolTip.showText(
                    global_pos,
                    warning_msg,
                    self.network_label,
                    QRect(),
                    5
                )

                self.showing_mismatch_tooltip = True

        else:

            if self.showing_mismatch_tooltip:

                QToolTip.hideText()

                self.showing_mismatch_tooltip = False
                
    def _setup_udp_watchdog(self):
        self.udp_watchdog_timer = QTimer(self)
        self.udp_watchdog_timer.setSingleShot(True)
        self.udp_watchdog_timer.timeout.connect(
            self._handle_udp_timeout
        )
        self.udp_watchdog_timer.start(6000)

    def handle_udp_status(
        self,
        device_id,
        esp_connected,
        esp_ssid,
        pc_ssid=None
    ):
        if device_id != self.udp_device_id:
            return

        self.udp_watchdog_timer.start(6000)
        self._handle_device_status(
            esp_connected,
            esp_ssid,
            pc_ssid
        )

    def _handle_udp_timeout(self):
        self.heartbeat_matches_pc = False
        self._handle_device_status(False, None)
        self.udp_watchdog_timer.start(6000)
        
    def set_online_status(self, is_online: bool):
        """Tracks online state changes and notifies the main window."""
        previous_status = getattr(self, "_device_online", None)
        self._device_online = is_online

        if previous_status != is_online:
            print(f"{self.system_name} online state changed: {previous_status} -> {is_online}")
            self.device_online_changed.emit(is_online)
            
    def start_setup_overlay(self):
        print("Opening WifiSetupOverlay")

        # --------------------------------------------------------
        # Capture the PC's current network BEFORE we switch it
        # to the ESP setup network.
        # --------------------------------------------------------

        target_ssid = read_pc_ssid()

        if not target_ssid or target_ssid == "No Wi-Fi":
            print("Cannot start Wi-Fi setup: PC is not connected.")
            return

        target_pw = WifiCredentialManager.get_password(target_ssid)

        if target_pw is None:
            print(
                f"Cannot start Wi-Fi setup: "
                f"password for '{target_ssid}' is unavailable."
            )
            return

        # --------------------------------------------------------
        # This is our credential snapshot.
        #
        # From this point onward, provisioning should use these
        # values even after the PC switches to the ESP setup AP.
        # --------------------------------------------------------

        print(
            f"Captured target Wi-Fi network: {target_ssid}"
        )

        self.overlay = WifiSetupOverlay(
            system_name=self.system_name,
            ap_ssid=self.ap_ssid,
            temp_pw=self.temp_pw,
            target_ssid=target_ssid,
            target_pw=target_pw
        )

        self.overlay.setup_completed.connect(
            self.handle_setup_success
        )

        self.overlay.show()

    def handle_setup_success(self, success: bool):
        
        self._setup_running = False
        
        self.set_online_status(success)
        
        self.connection_finished.emit(self.system_name, success)
    