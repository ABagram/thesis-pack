from PyQt6.QtWidgets import QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QToolTip
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRect
from PyQt6.QtGui import QFont, QIcon, QPixmap
from PyQt6 import sip
from load_icon import load_icon
from read_pc_ssid import read_pc_ssid
from wifi_setup_overlay import WifiSetupOverlay
from wifi_credential_manager import WifiCredentialManager

ICON_WARNING = "icons/warning.svg"
ICON_OFFLINE = "icons/globe_2_cancel.svg"
ICON_ONLINE = "icons/wifi.svg"

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
        temp_ssid: str | None,
        temp_pw: str | None,
        target_ssid: str,
        target_pw: str,
        disabled_tooltip: str = (
            "Target setup network not detected."
        ),
        device_host=None,
        udp_device_id: str | None = None,
        parent=None
    ):
        super().__init__(parent)
        
        self.showing_mismatch_tooltip = False
        
        self.system_name = system_name
        self.icon_path = icon_path
        self.temp_ssid = temp_ssid
        self.temp_pw = temp_pw
        self.target_ssid = target_ssid
        self.target_pw = target_pw
        self.disabled_tooltip = disabled_tooltip
        self.device_host = (device_host)
        self.udp_device_id = udp_device_id
        
        self.connected_network = None

        self.init_ui()

        if self.udp_device_id:
            self._setup_udp_watchdog()

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

        self.icon_label = QLabel()
        self.icon_label.setObjectName("SystemIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setPixmap(
            load_icon(
                self.icon_path,
                size=14,
                color="#64748b"
            )
        )
    
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
        self.connect_status.setPixmap(
    load_icon(ICON_OFFLINE, size=STATUS_ICON_SIZE, color="#DC2626")
)
        self.connect_status.setObjectName("Connect_Status_Offline")

        self.ssid_label = QLabel("SSID:")
        self.ssid_label.setStyleSheet("""
            font-size: 12px;
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

    def set_connected_network(self, ssid):
        self.connected_network = ssid

        if hasattr(self, "network_label"):
            self.network_label.setText(
                ssid or "Disconnected"
            )

    def _handle_device_status(
        self,
        esp_connected,
        esp_ssid,
        pc_ssid=None
    ):

        self.esp_ssid = esp_ssid

        self.set_connected_network(
            esp_ssid if esp_connected else None
        )

        if pc_ssid is None:
            pc_ssid = read_pc_ssid()

        is_valid_online = (
            esp_connected
            and pc_ssid == esp_ssid
        )

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
                f"{self.device_host}='{esp_ssid}'"
            )

            self.connect_status.setPixmap(
                load_icon(
                    ICON_WARNING,
                    size=STATUS_ICON_SIZE,
                    color="#f45900"
                )
            )

            self.network_label.setText(
                f"{esp_ssid} (Mismatch)"
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
        self._handle_device_status(False, None)
        self.udp_watchdog_timer.start(6000)
        
    def set_online_status(self, is_online: bool):
        """Updates the status badge and notifies the main window
        when the ESP online/offline state changes.
        """

        # --------------------------------------------------------
        # Track the previous state.
        # --------------------------------------------------------

        previous_status = getattr(
            self,
            "_device_online",
            None
        )

        self._device_online = is_online

        # --------------------------------------------------------
        # Update visual status.
        # --------------------------------------------------------

        if not hasattr(self, "connect_status"):
            return

        if sip.isdeleted(self.connect_status):
            return

        if is_online:

            self.connect_status.setPixmap(
                load_icon(
                    ICON_ONLINE,
                    size=STATUS_ICON_SIZE,
                    color="#16A34A"
                )
            )

            self.connect_status.setObjectName(
                "Connect_Status_Online"
            )

        else:

            self.connect_status.setPixmap(
                load_icon(
                    ICON_OFFLINE,
                    size=STATUS_ICON_SIZE,
                    color="#DC2626"
                )
            )

            self.connect_status.setObjectName(
                "Connect_Status_Offline"
            )

        # --------------------------------------------------------
        # Tell MainContentWidget only when the state actually
        # changes.
        #
        # This prevents repeated calls to poll_device_network()
        # from repeatedly starting/stopping the WLAN scanner.
        # --------------------------------------------------------

        if previous_status != is_online:

            print(
                f"{self.system_name} online state changed: "
                f"{previous_status} -> {is_online}"
            )

            self.device_online_changed.emit(
                is_online
            )
            
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
            temp_ssid=self.temp_ssid,
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
    